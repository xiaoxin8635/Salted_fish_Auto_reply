"""系统设置 ORM 模型(简单 KV 表)。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Setting(Base):
    """键值对配置表,存放杂项设置(告警 webhook、静默时段、限频参数等)。

    典型 key:dingtalk_webhook / wecom_webhook / silent_hours / rate_limit_per_min
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
