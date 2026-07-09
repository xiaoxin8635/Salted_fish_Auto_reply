"""ORM 模型聚合包。

本模块在导入时定义 ``TimestampMixin`` 并依次导入全部模型子模块,
使 SQLAlchemy 注册所有表。Alembic 的 ``env.py`` 通过
``import app.models`` 即可让 ``Base.metadata`` 包含全部表。
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base  # noqa: F401  (re-export 给 alembic env 使用)


class TimestampMixin:
    """通用时间戳列:``created_at`` 与 ``updated_at``。

    ``default`` / ``onupdate`` 接收可调用对象,每次插入/更新时取当前本地时间。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


# 导入各模型,触发表注册(必须在 TimestampMixin 定义之后)
from app.models.account import Account  # noqa: E402,F401
from app.models.message import Message  # noqa: E402,F401
from app.models.rule import Rule  # noqa: E402,F401
from app.models.llm_config import LlmConfig  # noqa: E402,F401
from app.models.log import Log  # noqa: E402,F401
from app.models.setting import Setting  # noqa: E402,F401

__all__ = [
    "Base",
    "TimestampMixin",
    "Account",
    "Message",
    "Rule",
    "LlmConfig",
    "Log",
    "Setting",
]
