"""消息处理器。

阶段 2:``echo_handler`` 回声处理器,用于验证收发链路。
阶段 3:将接入「关键词规则 → LLM → 兜底」回复引擎。
"""

from typing import Any

from loguru import logger

from app.core.types import IncomingMessage


async def echo_handler(live: Any, msg: IncomingMessage) -> None:
    """回声处理器:原样回显收到的消息(阶段 1/2 验证收发链路)。

    Args:
        live: 当前连接(PatchedXianyuLive 或 Mock),需提供 ``send`` 方法。
        msg: 解析后的入站消息。
    """
    logger.info(f"[echo] {msg.sender_name}({msg.sender_id})@{msg.cid}: {msg.text}")
    await live.send(msg.cid, msg.sender_id, f"收到:{msg.text}")
