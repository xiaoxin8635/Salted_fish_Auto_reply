"""Alembic 迁移环境配置。

连接应用自身的 SQLAlchemy ``Base.metadata`` 作为 ``target_metadata``,
并使用 ``app.config.settings`` 提供的数据库 URL。
对 SQLite 开启 batch 模式(``render_as_batch=True``),以支持 ALTER TABLE。
"""

from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# 将 backend/ 加入 sys.path,确保可 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402
import app.models  # noqa: E402,F401  (导入即注册全部表到 Base.metadata)

# Alembic 配置对象(读取 alembic.ini)
config = context.config

# 用应用的数据库 URL 覆盖 alembic.ini 中的占位值
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.effective_database_url)

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 迁移目标:应用的全部 ORM 元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式:仅生成 SQL 脚本,不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式:连接数据库并执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
