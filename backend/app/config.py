"""应用配置加载。

基于 pydantic-settings,优先级:环境变量 > 项目根 .env 文件 > 代码默认值。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录(本文件上两级:config.py -> app -> backend)
BACKEND_DIR = Path(__file__).resolve().parent.parent
# 项目根目录(Salted_fish_Auto_reply/)
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """全局配置。所有字段均可通过同名(大小写不敏感)环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 应用 ----
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8089

    # ---- 数据库 ----
    # 留空时使用 backend/data/app.sqlite(由 database_url_property 计算)
    database_url: str = ""

    # ---- LLM(OpenAI 兼容接口,阶段4启用) ----
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # ---- 告警 webhook(阶段6启用) ----
    dingtalk_webhook: str = ""
    wecom_webhook: str = ""

    # ---- 日志 ----
    log_level: str = "INFO"

    @property
    def data_dir(self) -> Path:
        """运行时数据目录(SQLite 文件、日志)。不存在则创建。"""
        d = BACKEND_DIR / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def effective_database_url(self) -> str:
        """实际使用的数据库 URL:显式配置优先,否则回退到本地 SQLite。"""
        if self.database_url:
            return self.database_url
        sqlite_path = (self.data_dir / "app.sqlite").as_posix()
        return f"sqlite:///{sqlite_path}"


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例(进程内缓存)。"""
    return Settings()
