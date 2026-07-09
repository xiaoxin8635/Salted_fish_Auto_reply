"""自定义异常定义。"""


class XianyuError(Exception):
    """闲鱼协议层与业务层异常的公共基类。"""


class CookieExpiredError(XianyuError):
    """Cookie 失效(获取 token 失败 / 鉴权失败)。

    触发后该账号 **不重试**,转入 ``COOKIE_EXPIRED`` 状态并告警,
    等待用户在前端重新粘贴 Cookie。
    """


class AccountStoppedError(XianyuError):
    """账号被用户主动停止(用于打断阻塞中的重连退避)。"""
