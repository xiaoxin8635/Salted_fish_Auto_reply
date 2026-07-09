"""vendor 协议库(cv-cat/XianYuApis)加载器。

背景:XianYuApis 的 ``utils/goofish_utils.py`` 在 **模块导入时** 用相对路径
``open('static/goofish_js_version_2.js')`` 读取签名 JS 并 ``execjs.compile``。
若工作目录不是 ``vendor/xianyu_apis/``,该相对路径会找不到文件导致 import 失败。

方案:首次 import 前 **临时切换工作目录** 到 ``vendor/xianyu_apis/``,
import 完成后恢复原目录。签名 JS 经 ``execjs.compile`` 编译进内存后,
后续 ``xianyu_js.call(...)`` 由 PyExecJS 写临时文件交由 node 执行,不再读盘,
因此工作目录恢复后不影响后续签名调用。

线程安全:``load_vendor`` 仅在应用启动时(单线程、同步)调用一次,无并发问题。
"""

import os
import sys
from typing import Any

from app.config import PROJECT_ROOT

#: vendor 协议库根目录
VENDOR_DIR = PROJECT_ROOT / "vendor" / "xianyu_apis"

_loaded = False

# 加载后填充的模块成员引用(类型用 Any,避免硬依赖 vendor 源码类型)
XianyuLive: Any = None
XianyuApis: Any = None
make_text: Any = None
make_image: Any = None
trans_cookies: Any = None


def load_vendor() -> None:
    """加载 vendor 协议库到当前进程(幂等,重复调用安全)。"""
    global _loaded, XianyuLive, XianyuApis, make_text, make_image, trans_cookies
    if _loaded:
        return

    if str(VENDOR_DIR) not in sys.path:
        sys.path.insert(0, str(VENDOR_DIR))

    old_cwd = os.getcwd()
    try:
        # 切到 vendor 目录,使 goofish_utils 的相对路径 'static/...' 可解析
        os.chdir(VENDOR_DIR)
        from goofish_live import XianyuLive as _XianyuLive  # noqa: E402
        from goofish_apis import XianyuApis as _XianyuApis  # noqa: E402
        from message import make_text as _make_text  # noqa: E402
        from message import make_image as _make_image  # noqa: E402
        from utils.goofish_utils import trans_cookies as _trans_cookies  # noqa: E402

        XianyuLive = _XianyuLive
        XianyuApis = _XianyuApis
        make_text = _make_text
        make_image = _make_image
        trans_cookies = _trans_cookies
    finally:
        os.chdir(old_cwd)

    _loaded = True


def get_xianyu_live_class() -> Any:
    """获取 vendor 的 XianyuLive 类(必要时先加载)。"""
    if not _loaded:
        load_vendor()
    return XianyuLive
