"""Parameter Sets 接口聚合入口。

各资源域的具体实现拆分在 parameter_sets_routers 子包中：
- sets   参数集及参数化检索 / 批量替换 / 候选识别
- items  参数项单项 CRUD 与引用查询

参数引用检索 / 替换 / 去参数化的纯逻辑已下沉至
services.parameter_reference_service。

路由地址 / 方法 / 请求响应与拆分前完全一致。为兼容既有的
`from api.v1.endpoints.parameter_sets import <name>` 引用，
在文件末尾重导出被外部使用的 schema 与工具函数。
"""
from fastapi import APIRouter

from api.v1.endpoints.parameter_sets_routers import sets, items

router = APIRouter()
router.include_router(sets.router)
router.include_router(items.router)

# ====== 兼容重导出（供 tests 及其它模块沿用旧的 import 路径） ======
from api.v1.endpoints.parameter_sets_routers._shared import (  # noqa: E402,F401
    ParameterItemSchema,
    _display_name_conflicts,
)
from services.parameter_reference_service import (  # noqa: E402,F401
    _body_matches_for_parameterize,
    _find_references_in_record,
    _pair_matches_for_parameterize,
    _replace_raw_text_for_parameterize,
)
