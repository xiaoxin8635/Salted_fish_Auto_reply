"""Orchestrator 单元测试:多账号编排、Cookie 失效隔离、状态回调。"""

import asyncio

import pytest

from app.core.orchestrator import Orchestrator
from app.core.reconnect import ReconnectPolicy
from app.enums import AccountStatus
from tests.helpers import wait_for
from tests.mock_xianyu import (
    MockLiveFactory,
    MockXianyuLive,
    behavior_cookie_expired,
    behavior_online,
)


def _policy(**kw) -> ReconnectPolicy:
    base = dict(base_delay=0.05, max_delay=0.2, max_attempts=5, jitter=0.0)
    base.update(kw)
    return ReconnectPolicy(**base)


def _factory_by_cookie(plans: dict) -> callable:
    """按 cookies 字符串分发不同行为的工厂。"""

    counters: dict[str, int] = {}

    def factory(cookies: str) -> MockXianyuLive:
        behs = plans.get(cookies, [None])
        idx = counters.get(cookies, 0)
        beh = behs[min(idx, len(behs) - 1)] if behs else None
        counters[cookies] = idx + 1
        return MockXianyuLive(cookies, on_main=beh)

    return factory


@pytest.mark.asyncio
async def test_start_two_accounts_both_online() -> None:
    """同时挂 2 个账号,均为 ONLINE。"""
    factory = MockLiveFactory([behavior_online])
    orch = Orchestrator(policy=_policy(), live_factory=factory)
    try:
        await orch.start("a1", "c1")
        await orch.start("a2", "c2")
        await wait_for(lambda: orch.online_count == 2, timeout=3.0)
        st = {s["account_id"]: s["status"] for s in orch.get_status()}
        assert st["a1"] == AccountStatus.ONLINE.value
        assert st["a2"] == AccountStatus.ONLINE.value
    finally:
        await orch.stop_all()


@pytest.mark.asyncio
async def test_cookie_expired_does_not_affect_other_account() -> None:
    """一个账号 Cookie 失效,不影响另一个账号在线(验收核心)。"""
    plans = {"bad": [behavior_cookie_expired], "good": [behavior_online]}
    factory = _factory_by_cookie(plans)
    orch = Orchestrator(policy=_policy(), live_factory=factory)
    try:
        await orch.start("a_bad", "bad")
        await orch.start("a_good", "good")
        await asyncio.sleep(0.3)
        st = {s["account_id"]: s["status"] for s in orch.get_status()}
        assert st["a_bad"] == AccountStatus.COOKIE_EXPIRED.value
        assert st["a_good"] == AccountStatus.ONLINE.value
    finally:
        await orch.stop_all()


@pytest.mark.asyncio
async def test_status_callback_invoked() -> None:
    """状态变更触发 on_status 回调。"""
    events: list[tuple[str, str]] = []

    async def on_status(account_id: str, status: AccountStatus) -> None:
        events.append((account_id, status.value))

    factory = MockLiveFactory([behavior_online])
    orch = Orchestrator(policy=_policy(), live_factory=factory, on_status=on_status)
    try:
        await orch.start("a1", "c1")
        await wait_for(lambda: any(s == AccountStatus.ONLINE.value for _, s in events), timeout=3.0)
    finally:
        await orch.stop_all()
    assert any(s == AccountStatus.ONLINE.value for _, s in events)
