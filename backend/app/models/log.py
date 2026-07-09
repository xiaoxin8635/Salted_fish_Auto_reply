"""系统日志 ORM 模型(供前端查看,与文件日志互补)。"""

from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import TimestampMixin


class Log(TimestampMixin, Base):
    """一条系统日志记录。

    created_at 继承自 TimestampMixin,前端按时间倒序查看。
    """

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 归属账号(NULL=系统级日志)
    account_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    # 级别:INFO / WARN / ERROR(LogLevel 大写常量)
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    # 分类:COOKIE / WS / LLM / RULE / RISK / SYSTEM(LogCategory 大写常量)
    category: Mapped[str] = mapped_column(String(16), default="SYSTEM")
    # 日志正文
    message: Mapped[str] = mapped_column(Text)
    # 异常堆栈(可选)
    trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
