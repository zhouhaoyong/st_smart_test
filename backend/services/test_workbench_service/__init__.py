"""测试工作台通用服务。

本模块已由单文件拆分为包，按职责分为 _shared / permissions / cleanup / dashboard 子模块。
此处门面重导出所有原对外暴露的名称，保证 `from services.test_workbench_service import <名称>` 全部沿用不变。
"""
from __future__ import annotations

from ._shared import *  # noqa: F401,F403
from .records import *  # noqa: F401,F403
from .permissions import *  # noqa: F401,F403
from .cleanup import *  # noqa: F401,F403
from .dashboard import *  # noqa: F401,F403
