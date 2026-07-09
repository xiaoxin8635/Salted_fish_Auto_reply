"""闲鱼自动回复程序 - 后端应用包。

分层结构:
    app.config     配置加载(pydantic-settings)
    app.db         数据库引擎 / 会话 / ORM 基类
    app.enums      全局枚举(前后端 + DB 统一大写)
    app.models     ORM 模型
    app.core       业务核心(编排 / 重连 / 回复引擎 / 风控 ...)
    app.patches    对 vendor 协议库的 monkey-patch
    app.api        REST + SSE 路由
"""

__version__ = "0.1.0"
