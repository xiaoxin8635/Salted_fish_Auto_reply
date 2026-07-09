"""闲鱼账号 ORM 模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import TimestampMixin


class Account(TimestampMixin, Base):
    """一个闲鱼账号(一个 Cookie = 一个值守实例)。"""

    __tablename__ = "accounts"

    # 主键:UUID 字符串(由业务层生成,便于多账号分布式扩展)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # 用户自定义昵称,如「小号A」
    name: Mapped[str] = mapped_column(String(64))
    # 原始 Cookie 串(MVP 明文存储,后续 TODO:改 Fernet 加密)
    cookies_raw: Mapped[str] = mapped_column(Text)
    # 从 Cookie 解析出的用户唯一标识(unb),用于防「回复自己」
    unb: Mapped[str] = mapped_column(String(64), index=True)
    # 是否启用(启用才会被 Orchestrator 拉起)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # 运行状态镜像:AccountStatus 大写常量(STARTING/ONLINE/RECONNECTING/...)
    status: Mapped[str] = mapped_column(String(20), default="STOPPED", index=True)
    # 最近一次在线时间
    last_online_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
