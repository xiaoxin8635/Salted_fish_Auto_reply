"""数据库引擎、会话工厂与 ORM 基类(SQLAlchemy 2.0 风格)。

SQLite 使用 WAL 模式以支持「多账号并发写 + 前端读」场景。
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite 需要 check_same_thread=False,否则多线程(如续期线程)访问会报错
_is_sqlite = settings.effective_database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.effective_database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""

    pass


# 对每个新建的 SQLite 连接自动开启外键约束与 WAL 相关 pragma
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
        """为每个 SQLite 连接开启外键约束,提升数据一致性。"""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db_wal() -> None:
    """对 SQLite 主库文件开启 WAL 模式(只需执行一次)。非 SQLite 跳过。"""
    if not _is_sqlite:
        return
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.commit()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖:为每个请求提供一个数据库会话,请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
