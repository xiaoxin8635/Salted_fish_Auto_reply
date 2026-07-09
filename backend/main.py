"""FastAPI 应用入口。

阶段0:仅提供健康检查,验证数据库连通性与依赖可用。
后续阶段在此挂载 Orchestrator(多账号编排)生命周期与各 API 路由。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app import __version__
from app.db import SessionLocal, init_db_wal


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期钩子。

    启动:初始化数据库(WAL 模式)。
    关闭:阶段2 起,在此优雅停止 Orchestrator 的所有账号运行时。
    """
    init_db_wal()
    yield


app = FastAPI(
    title="闲鱼自动回复程序",
    description="多账号值守 + 关键词/LLM 自动回复 + React 管理后台",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/api/status/health", tags=["status"])
def health() -> dict:
    """健康检查:返回应用版本与数据库连通性。"""
    db_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "version": __version__, "db": db_ok}
