"""FastAPI 应用入口。

生命周期管理 ``Orchestrator``(多账号编排中枢),并提供状态/账号启停 API。
阶段 5 将接入完整的账号 CRUD、消息查看、规则配置等管理后台 API。
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.core.orchestrator import Orchestrator
from app.db import SessionLocal, init_db_wal

# 全局编排器,在 lifespan 启动时创建、关闭时销毁
orchestrator: Optional[Orchestrator] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期:启动时初始化数据库与编排器,关闭时停止所有账号。"""
    global orchestrator
    init_db_wal()
    orchestrator = Orchestrator()
    yield
    if orchestrator is not None:
        await orchestrator.stop_all()


app = FastAPI(
    title="闲鱼自动回复程序",
    description="多账号值守 + 关键词/LLM 自动回复 + React 管理后台",
    version=__version__,
    lifespan=lifespan,
)


def _orch() -> Orchestrator:
    """获取编排器,未就绪时返回 503。"""
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator 尚未就绪")
    return orchestrator


# ---------------------------------------------------------------------- #
# 状态
# ---------------------------------------------------------------------- #
@app.get("/api/status/health", tags=["status"])
def health() -> dict:
    """健康检查:应用版本 + 数据库连通性 + 在线账号数。"""
    db_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    online = orchestrator.online_count if orchestrator is not None else 0
    return {"status": "ok", "version": __version__, "db": db_ok, "online_accounts": online}


@app.get("/api/accounts", tags=["accounts"])
def list_accounts() -> list[dict]:
    """返回所有账号的当前运行状态快照。"""
    return _orch().get_status()


# ---------------------------------------------------------------------- #
# 账号启停(临时 API,阶段 5 将替换为完整 CRUD + Cookie 持久化)
# ---------------------------------------------------------------------- #
class StartRequest(BaseModel):
    """启动账号请求体。"""
    cookies: str           # 从 goofish.com F12 复制的完整 Cookie 串
    name: Optional[str] = None  # 可选昵称(仅记录用)


@app.post("/api/accounts/{account_id}/start", tags=["accounts"])
async def start_account(account_id: str, req: StartRequest) -> dict:
    """启动(或重启)一个账号的值守。"""
    if not req.cookies or not req.cookies.strip():
        raise HTTPException(status_code=400, detail="cookies 不能为空")
    await _orch().start(account_id, req.cookies.strip())
    return {"account_id": account_id, "started": True}


@app.post("/api/accounts/{account_id}/stop", tags=["accounts"])
async def stop_account(account_id: str) -> dict:
    """停止一个账号的值守。"""
    ok = await _orch().stop(account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"account_id": account_id, "stopped": True}
