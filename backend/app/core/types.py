"""核心层共享数据结构。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IncomingMessage:
    """收到的一条闲鱼消息(已解密、已提取关键字段)。"""

    cid: str                                      # 会话 ID(@ 前部分)
    sender_id: str                                # 发送者用户 ID
    sender_name: str                              # 发送者昵称
    text: str                                     # 文本内容
    raw: dict = field(default_factory=dict)       # 原始解密结构(扩展用)
