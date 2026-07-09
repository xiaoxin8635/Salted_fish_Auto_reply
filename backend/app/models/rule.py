"""关键词规则 ORM 模型。"""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import TimestampMixin


class Rule(TimestampMixin, Base):
    """关键词自动回复规则。

    作用域:GLOBAL(全局,所有账号生效)或 ACCOUNT(账号专属,优先于全局)。
    匹配:EXACT(精确)/ CONTAINS(包含,默认)/ REGEX(正则)。
    """

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 作用域:GLOBAL / ACCOUNT(RuleScope 大写常量)
    scope: Mapped[str] = mapped_column(String(16), default="GLOBAL")
    # 账号 ID(scope=ACCOUNT 时必填,scope=GLOBAL 时为 NULL)
    account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # 匹配方式:EXACT / CONTAINS / REGEX(RuleMatchType 大写常量)
    match_type: Mapped[str] = mapped_column(String(16), default="CONTAINS")
    # 关键词(或正则表达式)
    keyword: Mapped[str] = mapped_column(String(255))
    # 命中后的回复文案
    reply_text: Mapped[str] = mapped_column(Text)
    # 优先级:数值越大越优先
    priority: Mapped[int] = mapped_column(Integer, default=0)
    # 是否启用
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
