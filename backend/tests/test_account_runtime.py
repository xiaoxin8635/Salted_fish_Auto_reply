"""AccountRuntime 单元测试:状态机、重连、Cookie 失效、消息处理。

全部用 MockXianyuLive,无需真实闲鱼连接。
"""

import asyncio

import pytest

from app.core.account_runtime import AccountRuntime
from app.core.reconnect import ReconnectPolicy
from app.enums import AccountStatus
from tests.helpers import wait_for, wait_for_state
from tests.mock_xianyu import (
    MockLiveFactory,
    behavior_disconnect,
    behavior_online,
    behavior_cookie_expired,
)


def _policy(**kw) -> ReconnectPolicy:
    """构造测试用快速重连策略。"""
    base = dict(base_delay=0.05, max_delay=0.2, max_attempts=5, jitter=0.0)
    base.update(kw)
    return ReconnectPolicy(**base)


@pytest.mark.asyncio
async def test_online_then_stop() -> None:
    """账号能进入 ONLINE,停止后变为 STOPPED。"""
    factory = MockLiveFactory([behavior_online])
    rt = AccountRuntime("a1", "ck", live_factory=factory, policy=_policy())
    task = asyncio.create_task(rt.run())
    try:
        await wait_for_state(rt, AccountStatus.ONLINE)
        assert rt.state == AccountStatus.ONLINE
    finally:
        rt.request_stop()
        await task
    assert rt.state == AccountStatus.STOPPED


@pytest.mark.asyncio
async def test_reconnect_after_network_disconnect() -> None:
    """网络断线后自动重连,恢复 ONLINE,且只创建 2 个 live(断 1 次重连 1 次)。"""
    factory = MockLiveFactory([behavior_disconnect, behavior_online])
    rt = AccountRuntime("a1", "ck", live_factory=factory, policy=_policy())
    task = asyncio.create_task(rt.run())
    try:
        await wait_for(lambda: len(factory.created) >= 2, timeout=3.0)
        await wait_for_state(rt, AccountStatus.ONLINE, timeout=3.0)
        assert rt.state == AccountStatus.ONLINE
    finally:
        rt.request_stop()
        await task
    assert len(factory.created) == 2


@pytest.mark.asyncio
async def test_cookie_expired_no_reconnect() -> None:
    """Cookie 失效不重连,直接转 COOKIE_EXPIRED 且只创建 1 个 live。"""
    factory = MockLiveFactory([behavior_cookie_expired])
    rt = AccountRuntime("a1", "ck", live_factory=factory, policy=_policy())
    await rt.run()  # Cookie 失效会立即退出
    assert rt.state == AccountStatus.COOKIE_EXPIRED
    assert len(factory.created) == 1


@pytest.mark.asyncio
async def test_message_handler_receives() -> None:
    """收到的消息会交给 handler。"""
    received: list[str] = []

    async def handler(live, msg) -> None:
        received.append(msg.text)

    factory = MockLiveFactory([behavior_online])
    rt = AccountRuntime("a1", "ck", live_factory=factory, message_handler=handler, policy=_policy())
    task = asyncio.create_task(rt.run())
    try:
        await wait_for_state(rt, AccountStatus.ONLINE)
        await factory.created[-1].deliver(text="你好")
        await wait_for(lambda: len(received) >= 1)
        assert received == ["你好"]
    finally:
        rt.request_stop()
        await task


@pytest.mark.asyncio
async def test_stop_interrupts_backoff() -> None:
    """停止信号能打断长退避(不会傻等 base_delay)。"""
    factory = MockLiveFactory([behavior_disconnect])  # 每次都断
    rt = AccountRuntime("a1", "ck", live_factory=factory, policy=_policy(base_delay=10.0))
    task = asyncio.create_task(rt.run())
    await wait_for_state(rt, AccountStatus.RECONNECTING, timeout=3.0)
    rt.request_stop()
    # 若 stop 无法打断退避,这里会超时
    await asyncio.wait_for(task, timeout=2.0)
    assert rt.state == AccountStatus.STOPPED


@pytest.mark.asyncio
async def test_fatal_gives_up_after_max_attempts() -> None:
    """持续致命错误超过 max_attempts 后转 FATAL。"""
    async def always_fail(live):
        raise RuntimeError("未知致命")
    factory = MockLiveFactory([always_fail])
    rt = AccountRuntime("a1", "ck", live_factory=factory, policy=_policy(max_attempts=3))
    task = asyncio.create_task(rt.run())
    try:
        await wait_for_state(rt, AccountStatus.FATAL, timeout=3.0)
    finally:
        rt.request_stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            pass
    assert rt.state == AccountStatus.FATAL
