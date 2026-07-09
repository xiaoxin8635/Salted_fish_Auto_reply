"""多账号编排器:单进程 asyncio 内管理 2~10 个 ``AccountRuntime``。

作为系统「中枢」:统一账号的启动 / 停止 / 重启 / 状态查询。
``live_factory`` 可注入,默认使用 ``PatchedXianyuLive``(真实协议层),
单元测试时可注入 ``MockXianyuLive`` 工厂。
"""

import asyncio
from typing import Any, Optional

from loguru import logger

from app.core.account_runtime import AccountRuntime, LiveFactory, MessageHandler
from app.core.handlers import echo_handler
from app.core.reconnect import ReconnectPolicy
from app.enums import AccountStatus


class Orchestrator:
    """多账号编排器(系统中枢)。"""

    def __init__(
        self,
        policy: Optional[ReconnectPolicy] = None,
        live_factory: Optional[LiveFactory] = None,
        message_handler: Optional[MessageHandler] = None,
        on_status=None,
        on_log=None,
    ) -> None:
        self._policy = policy or ReconnectPolicy()
        self._live_factory = live_factory or self._default_live_factory
        self._message_handler = message_handler or echo_handler
        self._on_status = on_status
        self._on_log = on_log
        self._runtimes: dict[str, AccountRuntime] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # 账号生命周期
    # ------------------------------------------------------------------ #
    async def start(
        self,
        account_id: str,
        cookies: str,
        message_handler: Optional[MessageHandler] = None,
    ) -> AccountStatus:
        """启动(或重启)一个账号的运行时。"""
        async with self._lock:
            existing = self._runtimes.get(account_id)
            if existing is not None:
                # 已存在则先停止旧运行时
                await self._stop_runtime(existing)

            runtime = AccountRuntime(
                account_id=account_id,
                cookies=cookies,
                live_factory=self._live_factory,
                message_handler=message_handler or self._message_handler,
                policy=self._policy,
                on_status=self._on_status,
                on_log=self._on_log,
            )
            self._runtimes[account_id] = runtime
            runtime._task = asyncio.create_task(runtime.run(), name=f"acct-{account_id}")
            logger.info(f"[orchestrator] 账号 {account_id} 已提交启动")
        return runtime.state

    async def stop(self, account_id: str) -> bool:
        """停止一个账号。返回是否找到了该账号。"""
        async with self._lock:
            runtime = self._runtimes.get(account_id)
        if runtime is None:
            return False
        await self._stop_runtime(runtime)
        logger.info(f"[orchestrator] 账号 {account_id} 已停止")
        return True

    async def stop_all(self) -> None:
        """停止所有账号(用于应用关闭)。"""
        runtimes = list(self._runtimes.values())
        for r in runtimes:
            r.request_stop()
        for r in runtimes:
            await self._stop_runtime(r, request=False)
        logger.info("[orchestrator] 所有账号已停止")

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def get_status(self) -> list[dict]:
        """返回所有账号的当前状态快照。"""
        return [
            {"account_id": rid, "status": r.state.value}
            for rid, r in self._runtimes.items()
        ]

    def get_runtime(self, account_id: str) -> Optional[AccountRuntime]:
        """获取指定账号的运行时(测试与调试用)。"""
        return self._runtimes.get(account_id)

    @property
    def online_count(self) -> int:
        """当前 ONLINE 状态的账号数。"""
        return sum(1 for r in self._runtimes.values() if r.state == AccountStatus.ONLINE)

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    async def _stop_runtime(self, runtime: AccountRuntime, request: bool = True) -> None:
        """停止并等待一个运行时退出。"""
        if request:
            runtime.request_stop()
        task = runtime._task
        if task is not None and not task.done():
            try:
                await task
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _default_live_factory(cookies: str) -> Any:
        """默认真实协议层工厂(延迟 import,避免测试时加载 vendor)。"""
        from app.patches.xianyu_live_patches import PatchedXianyuLive
        return PatchedXianyuLive(cookies)
