"""枚举常量定义。

约定:所有枚举值在「前端 / 后端 / 数据库」三层统一使用大写字符串,
不使用任何大小写转换器(converter)。数据库列以 String 存储大写常量值。
"""

from enum import StrEnum


class AccountStatus(StrEnum):
    """闲鱼账号运行状态,驱动前端徽标颜色与重连逻辑。"""

    STARTING = "STARTING"              # 正在建立连接
    ONLINE = "ONLINE"                  # 在线,正常收发
    RECONNECTING = "RECONNECTING"      # 断线后指数退避重连中
    COOKIE_EXPIRED = "COOKIE_EXPIRED"  # Cookie 失效,不重试,等待重新粘贴
    STOPPED = "STOPPED"                # 用户主动停止
    FATAL = "FATAL"                    # 未知致命错误,已停止该账号


class MessageDirection(StrEnum):
    """消息方向。"""

    INBOUND = "INBOUND"    # 收到(买家发来)
    OUTBOUND = "OUTBOUND"  # 发出(程序回复)


class MessageType(StrEnum):
    """消息内容类型。"""

    TEXT = "TEXT"
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    SYSTEM = "SYSTEM"


class ReplySource(StrEnum):
    """自动回复来源(仅对 OUTBOUND 消息有效)。"""

    RULE = "RULE"            # 命中关键词规则
    LLM = "LLM"              # 大模型生成
    FALLBACK = "FALLBACK"    # 兜底文案
    SUPPRESSED = "SUPPRESSED"  # 被风控拦截,未实际发送


class RuleScope(StrEnum):
    """关键词规则作用域。"""

    GLOBAL = "GLOBAL"      # 全局规则,所有账号生效
    ACCOUNT = "ACCOUNT"    # 账号专属规则(优先于全局)


class RuleMatchType(StrEnum):
    """关键词匹配方式。"""

    EXACT = "EXACT"          # 精确相等
    CONTAINS = "CONTAINS"   # 包含子串(默认)
    REGEX = "REGEX"         # 正则匹配


class LogLevel(StrEnum):
    """日志级别。"""

    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class LogCategory(StrEnum):
    """日志分类,便于在前端按模块筛选。"""

    COOKIE = "COOKIE"   # Cookie 鉴权相关
    WS = "WS"           # WebSocket 连接 / 重连
    LLM = "LLM"         # 大模型调用
    RULE = "RULE"       # 规则匹配
    RISK = "RISK"       # 风控
    SYSTEM = "SYSTEM"   # 系统级
