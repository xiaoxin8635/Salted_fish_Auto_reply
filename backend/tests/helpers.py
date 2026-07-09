"""测试辅助函数。"""

import asyncio
import time
from typing import Callable


async def wait_for(predicate: Callable[[], bool], timeout: float = 2.0, interval: float = 0.01) -> bool:
    """轮询等待条件成立,超时抛 AssertionError。"""
    deadline = time.monotonic() + timeout
    while not predicate():
        await asyncio.sleep(interval)
        if time.monotonic() > deadline:
            raise AssertionError(f"等待条件超时({timeout}s)")
    return True


async def wait_for_state(runtime, target, timeout: float = 2.0) -> bool:
    """等待 AccountRuntime 进入目标状态。"""
    return await wait_for(lambda: runtime.state == target, timeout=timeout)
