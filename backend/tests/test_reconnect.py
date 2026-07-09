"""ReconnectPolicy 单元测试(纯逻辑,无 IO)。"""

import pytest

from app.core.reconnect import Cause, ReconnectPolicy
from app.errors import CookieExpiredError


class TestClassify:
    """异常分类测试。"""

    def test_cookie_expired(self) -> None:
        assert ReconnectPolicy.classify(CookieExpiredError("x")) == Cause.COOKIE_EXPIRED

    def test_network_oserror(self) -> None:
        assert ReconnectPolicy.classify(OSError("断线")) == Cause.NETWORK

    def test_network_connection_error(self) -> None:
        assert ReconnectPolicy.classify(ConnectionError("x")) == Cause.NETWORK

    def test_network_timeout(self) -> None:
        assert ReconnectPolicy.classify(TimeoutError("超时")) == Cause.NETWORK

    def test_websockets_exception_is_network(self) -> None:
        websockets = pytest.importorskip("websockets")
        assert ReconnectPolicy.classify(websockets.ConnectionClosed(None, None)) == Cause.NETWORK

    def test_fatal_runtime_error(self) -> None:
        assert ReconnectPolicy.classify(RuntimeError("未知")) == Cause.FATAL

    def test_none_is_network(self) -> None:
        assert ReconnectPolicy.classify(None) == Cause.NETWORK


class TestNextDelay:
    """退避计算测试。"""

    def test_exponential_increase(self) -> None:
        p = ReconnectPolicy(base_delay=5.0, factor=2.0, jitter=0.0, max_delay=10_000.0)
        assert p.next_delay(1) == 5.0
        assert p.next_delay(2) == 10.0
        assert p.next_delay(3) == 20.0

    def test_capped_by_max_delay(self) -> None:
        p = ReconnectPolicy(base_delay=5.0, factor=2.0, jitter=0.0, max_delay=15.0, max_attempts=10)
        # 第3次本应 20s,被 15s 封顶
        assert p.next_delay(3) == 15.0
        # 第5次仍在 max_attempts 范围内,且被 max_delay 封顶
        assert p.next_delay(5) == 15.0

    def test_returns_none_when_exceeds_max_attempts(self) -> None:
        p = ReconnectPolicy(max_attempts=3)
        assert p.next_delay(4) is None
        assert p.next_delay(3) is not None  # 第3次仍在范围内

    def test_jitter_within_range(self) -> None:
        p = ReconnectPolicy(base_delay=100.0, factor=1.0, jitter=0.3, max_delay=10_000.0)
        for _ in range(50):
            d = p.next_delay(1)
            assert 70.0 <= d <= 130.0  # 100 ± 30%
