"""pytest 全局配置:确保 backend/ 在 import 路径最前。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
