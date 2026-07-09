"""测试用 MockXianyuLive:可编程的协议层替身。

无需真实闲鱼连接即可测试 AccountRuntime / Orchestrator 的重连、状态机、
多账号编排与 Cookie 失效隔离。通过 ``on_main`` 回调控制每次连接的行为
(稳定在线 / 断线 / Cookie 失效 / 投递消息)。
"""

import asyncio
from typing import Awaitable, Callable, Optional, Union, List

from app.core.types import IncomingMessage
from app.errors import CookieExpiredError

#: 连接行为签名
Behavior = Callable[["MockXianyuLive"], Awaitable[None]]


class MockXianyuLive:
    """XianyuLive 的测试替身,实现 AccountRuntime 所需接口。"""

    def __init__(
        self,
        cookies: str,
        *,
        on_main: Optional[Behavior] = None,
        myid: str = "me",
    ) -> None:
        self.cookies = cookies
        self.myid = myid
        self.on_main = on_main
        self._handler = None
        #: 记录所有 send 调用,便于断言回复内容
        self.sent: List[dict] = []
        self.closed = False
        #: main 被调用次数(=连接次数)
        self.connection_count = 0
        self._stop = asyncio.Event()

    # ---- AccountRuntime 所需接口 ----
    def set_message_handler(self, handler) -> None:
        self._handler = handler

    async def send(self, cid: str, to_id: str, text: str) -> None:
        self.sent.append({"cid": cid, "to_id": to_id, "text": text})

    async def main(self) -> None:
        self.connection_count += 1
        self.closed = False
        self._stop.clear()
        if self.on_main is not None:
            await self.on_main(self)
        else:
            # 默认:稳定在线,阻塞直到 close
            await self._stop.wait()

    async def close(self) -> None:
        self.closed = True
        self._stop.set()

    # ---- 测试辅助 ----
    async def deliver(
        self, *, sender_id: str = "buyer1", sender_name: str = "买家",
        text: str = "在吗", cid: str = "c1",
    ) -> None:
        """模拟收到一条买家消息,触发已设置的 handler。"""
        if self._handler is None:
            return
        msg = IncomingMessage(cid=cid, sender_id=sender_id, sender_name=sender_name, text=text)
        await self._handler(self, msg)


class MockLiveFactory:
    """live 工厂:按队列依次返回配置好行为的 Mock。

    队列耗尽后,复用最后一个 behavior(便于「先断后通」等场景)。
    """

    def __init__(self, behaviors: Union[Behavior, List[Optional[Behavior]], None] = None) -> None:
        if behaviors is None:
            self._behaviors: List[Optional[Behavior]] = []
        elif callable(behaviors):
            self._behaviors = [behaviors]
        else:
            self._behaviors = list(behaviors)
        self.created: List[MockXianyuLive] = []
        self._idx = 0

    def __call__(self, cookies: str) -> MockXianyuLive:
        if not self._behaviors:
            beh = None
        elif self._idx < len(self._behaviors):
            beh = self._behaviors[self._idx]
        else:
            beh = self._behaviors[-1]
        self._idx += 1
        live = MockXianyuLive(cookies, on_main=beh)
        self.created.append(live)
        return live


# ---- 可复用行为 ----

async def behavior_online(live: MockXianyuLive) -> None:
    """稳定在线:阻塞直到 close。"""
    await live._stop.wait()


async def behavior_disconnect(live: MockXianyuLive) -> None:
    """连接建立后立即断线(抛网络异常,归类为 NETWORK)。"""
    raise OSError("模拟网络断线")


async def behavior_cookie_expired(live: MockXianyuLive) -> None:
    """Cookie 失效:抛 CookieExpiredError(不重试)。"""
    raise CookieExpiredError("模拟 Cookie 失效")
