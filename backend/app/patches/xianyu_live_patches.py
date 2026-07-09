"""对 vendor ``XianyuLive`` 的子类化扩展:``PatchedXianyuLive``。

修复 vendor 源码的若干致命缺陷(详见实现计划阶段 1/2):

1. ``init()`` 中 token 获取失败时 ``exit(0)`` → 改为 ``raise CookieExpiredError``
2. ``websockets.connect`` 增加 ``ping_interval/ping_timeout/close_timeout``,避免静默断线
3. 续期线程(``user_alive``)改为可控停止(``threading.Event``),不再 ``while True`` 泄漏
4. ``handle_message`` 整体重写:解密提取 → 防回自己 → 交给业务 handler(不再 ``except: pass``)
5. 新增 ``close()``:优雅关闭 ws + 停续期线程
6. 每条消息处理用 ``create_task`` 包一层,防 handler(LLM 等)阻塞消息主循环
7. ``init`` 改为 ``await`` 同步执行,token 失败能直接冒泡到外层重连循环

vendor 源码不改,全部通过子类 override 实现,便于跟进上游。
"""

import asyncio
import json
import threading
import time
from typing import Any, Awaitable, Callable, Optional, TYPE_CHECKING

from loguru import logger

from app.errors import CookieExpiredError
from app.vendor_loader import VENDOR_DIR, load_vendor

import sys as _sys

if str(VENDOR_DIR) not in _sys.path:
    _sys.path.insert(0, str(VENDOR_DIR))

# 触发 vendor 加载(在正确工作目录下编译签名 JS 到内存)
load_vendor()

import websockets  # noqa: E402
from utils.goofish_utils import (  # noqa: E402
    generate_mid,
    decrypt,
    get_session_cookies_str,
)
from app.vendor_loader import get_xianyu_live_class  # noqa: E402
from app.core.types import IncomingMessage  # noqa: E402

if TYPE_CHECKING:
    pass

#: vendor 的 XianyuLive 基类
XianyuLive = get_xianyu_live_class()

#: 业务消息处理器签名:(live, msg) -> Awaitable[None]
MessageHandler = Callable[["PatchedXianyuLive", IncomingMessage], Awaitable[None]]

#: WebSocket 握手请求头(复刻 vendor,Origin 指向 goofish)
_WS_HEADERS = {
    "Host": "wss-goofish.dingtalk.com",
    "Connection": "Upgrade",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    ),
    "Origin": "https://www.goofish.com",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

#: 闲鱼 IM app-key(复刻 vendor)
_APP_KEY = "444e9908a51d1cb236a27862abc769c9"


class PatchedXianyuLive(XianyuLive):
    """可生产用的 XianyuLive 子类:修复致命缺陷 + 可控生命周期 + 业务 handler 接入。"""

    def __init__(self, cookies_str: str) -> None:
        super().__init__(cookies_str)
        # 当前 WebSocket 连接(main 运行期间持有)
        self._ws: Any = None
        # 业务消息处理器
        self._message_handler: Optional[MessageHandler] = None
        # 停止信号:close() 触发,用于打断退避等待
        self._stop_event = asyncio.Event()
        # 续期线程停止信号(跨线程)
        self._alive_stop = threading.Event()
        self._alive_started = False

    # ------------------------------------------------------------------ #
    # 业务接入
    # ------------------------------------------------------------------ #
    def set_message_handler(self, handler: MessageHandler) -> None:
        """设置业务消息处理器(收到买家消息时回调)。"""
        self._message_handler = handler

    async def send(self, cid: str, to_id: str, text: str) -> None:
        """发送文本消息(业务层调用,使用当前连接)。"""
        if self._ws is None:
            raise RuntimeError("WebSocket 未连接,无法发送消息")
        from app.vendor_loader import make_text
        await self.send_msg(self._ws, cid, to_id, make_text(text))

    # ------------------------------------------------------------------ #
    # override: token 失败抛异常而非 exit(0)
    # ------------------------------------------------------------------ #
    async def init(self, ws) -> None:  # type: ignore[override]
        """注册连接:获取 token、发 /reg 与 ackDiff。token 失败则抛 CookieExpiredError。"""
        data = self.xianyu.get_token()
        token = ""
        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, dict):
                token = inner.get("accessToken", "") or ""
        if not token:
            raise CookieExpiredError("获取 token 失败,Cookie 可能已过期")

        # /reg 注册(复刻 vendor)
        reg = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": _APP_KEY,
                "token": token,
                "ua": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 "
                    "DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/133.0.0.0) "
                    "DingWeb/2.1.5 IMPaaS DingWeb/2.1.5"
                ),
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": self.device_id,
                "mid": generate_mid(),
            },
        }
        await ws.send(json.dumps(reg))

        # ackDiff(复刻 vendor)
        current_time = int(time.time() * 1000)
        ack_diff = {
            "lwp": "/r/SyncStatus/ackDiff",
            "headers": {"mid": generate_mid()},
            "body": [
                {
                    "pipeline": "sync",
                    "tooLong2Tag": "PNM,1",
                    "channel": "sync",
                    "topic": "sync",
                    "highPts": 0,
                    "pts": current_time * 1000,
                    "seq": 0,
                    "timestamp": current_time,
                }
            ],
        }
        await ws.send(json.dumps(ack_diff))
        logger.info(f"[XianyuLive] init 完成 (unb={self.myid})")

    # ------------------------------------------------------------------ #
    # override: 可控续期线程(不再 while True 泄漏)
    # ------------------------------------------------------------------ #
    def user_alive(self) -> None:  # type: ignore[override]
        """续期线程:每 600s 刷新 token;收到停止信号及时退出。"""
        while not self._alive_stop.wait(600):
            if self._alive_stop.is_set():
                break
            try:
                self.xianyu.refresh_token()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[XianyuLive] refresh_token 失败: {e}")

    def _start_alive_thread(self) -> None:
        """启动续期线程(实例级去重)。"""
        if self._alive_started:
            return
        self._alive_started = True
        threading.Thread(
            target=self.user_alive,
            name=f"xianyu-alive-{self.myid}",
            daemon=True,
        ).start()

    # ------------------------------------------------------------------ #
    # override: 带心跳的消息循环,断线抛异常冒泡到外层重连
    # ------------------------------------------------------------------ #
    async def main(self) -> None:  # type: ignore[override]
        """建立连接并运行消息循环;断线或停止时抛异常/返回,交由外层决策。"""
        headers = dict(_WS_HEADERS)
        headers["Cookie"] = get_session_cookies_str(self.xianyu.session)
        self._start_alive_thread()

        async with websockets.connect(
            self.base_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as websocket:
            self._ws = websocket
            # 同步 init:token 失败直接抛 CookieExpiredError
            await self.init(websocket)
            # 心跳(继承 vendor 的 heart_beat)
            heartbeat_task = asyncio.create_task(self.heart_beat(websocket))
            try:
                async for raw in websocket:
                    try:
                        message = json.loads(raw)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"[XianyuLive] 非 JSON 消息,跳过: {e}")
                        continue
                    await self._ack(websocket, message)
                    await self.handle_message(message, websocket)
            finally:
                heartbeat_task.cancel()
                self._ws = None

    async def _ack(self, websocket, message: dict) -> None:
        """对服务端消息回 ack(复刻 vendor 行为,可安全失败)。"""
        headers = message.get("headers") if isinstance(message, dict) else None
        if not isinstance(headers, dict):
            return
        ack: dict = {
            "code": 200,
            "headers": {
                "mid": headers.get("mid") or generate_mid(),
                "sid": headers.get("sid", ""),
            },
        }
        for key in ("app-key", "ua", "dt"):
            if key in headers:
                ack["headers"][key] = headers[key]
        try:
            await websocket.send(json.dumps(ack))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[XianyuLive] ack 发送失败(可忽略): {e}")

    # ------------------------------------------------------------------ #
    # override: 解密提取 + 防回自己 + 交给业务 handler(不再 except: pass)
    # ------------------------------------------------------------------ #
    async def handle_message(self, message: dict, websocket) -> None:  # type: ignore[override]
        """解密消息并提取关键字段,交给业务 handler。"""
        # 仅处理推送类消息
        try:
            data = message["body"]["syncPushPackage"]["data"][0]["data"]
        except (KeyError, IndexError, TypeError):
            return

        # data 可能已是明文 JSON 字符串,也可能是需解密的 base64
        decoded: Optional[dict] = None
        if isinstance(data, str):
            try:
                decoded = json.loads(data)
            except json.JSONDecodeError:
                decoded = None
        if decoded is None:
            try:
                decoded = json.loads(decrypt(data))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[XianyuLive] 消息解密失败,跳过: {e}")
                return

        try:
            ext = decoded["1"]["10"]
            cid_full = decoded["1"]["2"]
        except (KeyError, TypeError):
            return

        cid = str(cid_full).split("@")[0]
        sender_id = str(ext.get("senderUserId", ""))
        sender_name = str(ext.get("reminderTitle", ""))
        text = str(ext.get("reminderContent", ""))

        # 防回自己(避免回声死循环)
        if not sender_id or sender_id == str(self.myid):
            return

        msg = IncomingMessage(
            cid=cid, sender_id=sender_id, sender_name=sender_name, text=text, raw=decoded
        )

        if self._message_handler is None:
            logger.debug(f"[XianyuLive] 未设置 handler,丢弃消息: cid={cid} from={sender_name}")
            return

        # create_task 包一层,防 handler 阻塞消息主循环
        asyncio.create_task(self._safe_dispatch(msg))

    async def _safe_dispatch(self, msg: IncomingMessage) -> None:
        """安全调用业务 handler,捕获并记录异常(避免吞没)。"""
        try:
            handler = self._message_handler
            if handler is not None:
                await handler(self, msg)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"[XianyuLive] 消息处理异常: {e}")

    # ------------------------------------------------------------------ #
    # 新增: 优雅关闭(幂等)
    # ------------------------------------------------------------------ #
    async def close(self) -> None:
        """关闭连接并停止续期线程。可重复调用,幂等。"""
        self._stop_event.set()
        self._alive_stop.set()
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
