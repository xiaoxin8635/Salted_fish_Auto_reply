"""断线重连策略与异常分类。

``ReconnectPolicy`` 负责指数退避计算与异常归类;
``Cause`` 决定是否重试、是否告警、账号转入何种状态。
"""

import asyncio
import random
from enum import StrEnum
from typing import Optional


class Cause(StrEnum):
    """断线原因分类。"""

    NETWORK = "NETWORK"                # 网络抖动 / 断开 → 退避重试
    COOKIE_EXPIRED = "COOKIE_EXPIRED"  # Cookie 失效 → 不重试,告警,转 COOKIE_EXPIRED
    FATAL = "FATAL"                    # 未知致命错误 → 告警,停该账号(不影响其他)
    STOPPED = "STOPPED"                # 用户主动停止 → 不重试


def _collect_network_exc_types() -> tuple[type, ...]:
    """收集「网络类」异常类型(websockets 未必一定可用,安全收集)。"""
    types: list[type] = [TimeoutError, OSError, ConnectionError]
    try:
        import websockets  # type: ignore

        types.append(websockets.WebSocketException)
    except Exception:
        # websockets 未安装(如纯单元测试环境)时跳过
        pass
    return tuple(types)


#: 网络类异常类型集合(模块级计算一次)
NETWORK_EXCEPTIONS = _collect_network_exc_types()


class ReconnectPolicy:
    """指数退避重连策略。

    - ``base_delay`` 起步等待秒数
    - ``max_delay`` 单次等待上限
    - ``max_attempts`` 网络类重试上限(超过则放弃,转 FATAL)
    - ``factor`` 倍增因子
    - ``jitter`` 抖动比例(±),避免多账号同步重连风暴
    """

    def __init__(
        self,
        base_delay: float = 5.0,
        max_delay: float = 300.0,
        max_attempts: int = 50,
        factor: float = 2.0,
        jitter: float = 0.3,
    ) -> None:
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts
        self.factor = factor
        self.jitter = jitter

    def next_delay(self, attempt: int) -> Optional[float]:
        """计算第 ``attempt`` 次重连前的等待秒数;超过上限返回 None(放弃)。"""
        if attempt > self.max_attempts:
            return None
        delay = min(self.base_delay * (self.factor ** (attempt - 1)), self.max_delay)
        delta = delay * self.jitter
        # 抖动后向下取到 0,避免负值
        return max(0.0, delay + random.uniform(-delta, delta))

    @staticmethod
    def classify(exc: BaseException | None) -> Cause:
        """根据异常类型归类断线原因。"""
        from app.errors import CookieExpiredError

        if exc is None:
            return Cause.NETWORK
        if isinstance(exc, CookieExpiredError):
            return Cause.COOKIE_EXPIRED
        if isinstance(exc, asyncio.CancelledError):
            return Cause.STOPPED
        if isinstance(exc, NETWORK_EXCEPTIONS):
            return Cause.NETWORK
        return Cause.FATAL
