"""LLM 配置 ORM 模型(全局默认 + 账号覆盖)。"""

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import TimestampMixin


class LlmConfig(TimestampMixin, Base):
    """大模型配置。

    ``account_id`` 为 NULL 表示「全局默认」;非空表示「账号专属覆盖」。
    查询时先查账号专属,无则回退全局(YAGNI:避免每账号重复配置)。
    """

    __tablename__ = "llm_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # NULL=全局默认;非空=账号覆盖
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # OpenAI 兼容接口地址
    base_url: Mapped[str] = mapped_column(String(255))
    # API Key(MVP 明文存储,TODO:改 Fernet 加密)
    api_key_enc: Mapped[str] = mapped_column(Text)
    # 模型名,如 deepseek-chat / gpt-4o-mini / qwen-plus
    model: Mapped[str] = mapped_column(String(64))
    # 系统提示词(含话术约束:防乱承诺、不透露 AI 身份)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 采样温度
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    # 单次请求超时(秒)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=15)
    # 是否启用
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
