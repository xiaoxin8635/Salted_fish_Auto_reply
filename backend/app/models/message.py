"""消息记录 ORM 模型(收发消息持久化)。"""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import TimestampMixin


class Message(TimestampMixin, Base):
    """一条收到的(INBOUND)或发出的(OUTBOUND)消息。"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 归属账号,删除账号时级联删除消息
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    # 会话 ID(cid,@goofish 前的部分)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    # 发送者用户 ID
    sender_id: Mapped[str] = mapped_column(String(64))
    # 发送者昵称
    sender_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 方向:INBOUND / OUTBOUND(MessageDirection 大写常量)
    direction: Mapped[str] = mapped_column(String(16))
    # 文本内容(图片/语音暂存原始 URL 或描述)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 消息类型:TEXT / IMAGE / AUDIO / SYSTEM(MessageType 大写常量)
    msg_type: Mapped[str] = mapped_column(String(16), default="TEXT")
    # 回复来源(仅 OUTBOUND):RULE / LLM / FALLBACK / SUPPRESSED(ReplySource 大写常量)
    source: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    # 原始解密 JSON,调试用
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
