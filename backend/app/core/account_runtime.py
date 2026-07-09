"""单账号运行时:封装一个账号的完整生命周期与断线重连。

``AccountRuntime.run()`` 是一个外层重连循环:每轮新建 live 实例并运行其消息循环,
断线后由 ``ReconnectPolicy`` 决定是否重试、退避多久。状态变更通过回调上报给
``Orchestrator``(用于同步 DB、广播 SSE)。

``AccountRuntime`` 不直接依赖真实 ``PatchedXianyuLive``,而是通过 ``live_factory``
注入,因此可用 ``MockXianyuLive`` 进行单元测试(无需真实闲鱼连接)。
"""

import asyncio
import inspect
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from app.core.handlers import echo_handler
from app.core.reconnect import Cause, ReconnectPolicy
from app.core.types import IncomingMessage
from app.enums import AccountStatus, LogCategory, LogLevel
from app.errors import CookieExpiredError

#: live 工厂签名:cookies -> live 实例(需实现 set_message_handler / main / close / myid)
LiveFactory = Callable[[str], Any]
#: 消息处理器签名:(live, msg) -> Awaitable[None]
MessageHandler = Callable[[Any, IncomingMessage], Awaitable[None]]
#: 状态回调签名(可同步可异步):(account_id, status) -> Any
StatusCallback = Callable[[str, AccountStatus], Any]
#: 日志回调签名(可同步可异步):(account_id, level, category, message) -> Any
LogCallback = Callable[[str, LogLevel, LogCategory, str], Any]


class AccountRuntime:
    """单个闲鱼账号的运行时(含断线重连与状态机)。"""

    def __init__(
        self,
        account_id: str,
        cookies: str,
        live_factory: LiveFactory,
        message_handler: Optional[MessageHandler] = None,
        policy: Optional[ReconnectPolicy] = None,
        on_status: Optional[StatusCallback] = None,
        on_log: Optional[LogCallback] = None,
    ) -> None:
        self.account_id = account_id
        self._cookies = cookies
        self._live_factory = live_factory
        self._message_handler = message_handler or echo_handler
        self._policy = policy or ReconnectPolicy()
        self._on_status = on_status
        self._on_log = on_log

        self._state: AccountStatus = AccountStatus.STOPPED
        self._stopping = False
        self._stop_event = asyncio.Event()
        self._live: Any = None
        self._task: Optional[asyncio.Task] = None
        self._attempt = 0

    @property
    def state(self) -> AccountStatus:
        """当前运行状态。"""
        return self._state

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    def request_stop(self) -> None:
        """请求停止(异步生效):设标志并关闭当前连接以打断阻塞中的 main。"""
        self._stopping = True
        self._stop_event.set()
        live = self._live
        if live is not None:
            asyncio.create_task(self._safe_close(live))

    async def run(self) -> None:
        """运行重连循环,直到停止 / Cookie 失效 / 致命错误 / 重连超上限。"""
        while True:
            if self._stopping:
                await self._set_state(AccountStatus.STOPPED)
                return

            cause = await self._run_once()

            if cause == Cause.STOPPED:
                await self._set_state(AccountStatus.STOPPED)
                return
            if cause == Cause.COOKIE_EXPIRED:
                await self._set_state(AccountStatus.COOKIE_EXPIRED)
                await self._log(LogLevel.ERROR, LogCategory.COOKIE, "Cookie 失效,等待重新粘贴")
                return
            if cause == Cause.FATAL:
                await self._set_state(AccountStatus.FATAL)
                await self._log(LogLevel.ERROR, LogCategory.WS, "致命错误,账号已停止")
                return

            # NETWORK:退避后重连
            self._attempt += 1
            await self._set_state(AccountStatus.RECONNECTING)
            delay = self._policy.next_delay(self._attempt)
            if delay is None:
                await self._set_state(AccountStatus.FATAL)
                await self._log(
                    LogLevel.ERROR, LogCategory.WS,
                    f"连续重连超过上限({self._policy.max_attempts}次),放弃",
                )
                return
            await self._log(LogLevel.WARN, LogCategory.WS, f"第 {self._attempt} 次重连,等待 {delay:.1f}s")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                # 被停止信号打断
                await self._set_state(AccountStatus.STOPPED)
                return
            except asyncio.TimeoutError:
                # 退避结束,进入下一轮重连
                continue

    async def _run_once(self) -> Cause:
        """运行一次连接生命周期,返回断线原因分类。"""
        live: Any = None
        try:
            await self._set_state(AccountStatus.STARTING)
            live = self._live_factory(self._cookies)
            self._live = live
            live.set_message_handler(self._message_handler)
            # 即将进入消息循环:连接已成功建立,重置连续失败计数
            # (避免稳定账号因偶发断线累积到 max_attempts 被误判 FATAL)
            self._attempt = 0
            await self._set_state(AccountStatus.ONLINE)
            await live.main()
            # main 正常返回:视作断线或主动停止
            return Cause.STOPPED if self._stopping else Cause.NETWORK
        except asyncio.CancelledError:
            return Cause.STOPPED
        except CookieExpiredError as e:
            await self._log(LogLevel.ERROR, LogCategory.COOKIE, f"Cookie 失效: {e}")
            return Cause.COOKIE_EXPIRED
        except Exception as e:  # noqa: BLE001
            if self._stopping:
                return Cause.STOPPED
            cause = self._policy.classify(e)
            await self._log(LogLevel.WARN, LogCategory.WS, f"连接异常({cause.value}): {e}")
            return cause
        finally:
            self._live = None
            if live is not None:
                await self._safe_close(live)

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    async def _set_state(self, status: AccountStatus) -> None:
        if self._state == status:
            return
        self._state = status
        if self._on_status is not None:
            await self._maybe_await(self._on_status(self.account_id, status))

    async def _log(self, level: LogLevel, category: LogCategory, message: str) -> None:
        fn = {
            LogLevel.INFO: logger.info,
            LogLevel.WARN: logger.warning,
            LogLevel.ERROR: logger.error,
        }[level]
        fn(f"[{self.account_id}] {message}")
        if self._on_log is not None:
            await self._maybe_await(self._on_log(self.account_id, level, category, message))

    @staticmethod
    async def _maybe_await(result: Any) -> None:
        """统一处理同步/异步回调。"""
        if inspect.isawaitable(result):
            await result

    @staticmethod
    async def _safe_close(live: Any) -> None:
        """安全关闭 live(幂等,吞异常)。"""
        try:
            r = live.close()
            if inspect.isawaitable(r):
                await r
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[runtime] 关闭 live 异常(可忽略): {e}")
