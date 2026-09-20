"""智测 Tools API 聚合入口。

各功能模块的具体实现拆分在 tools_routers 子包中：
- text_tools   请求代理 / 身份证生成 / 翻译 / 文本对比 / URL 编解码 / 时间戳
- curl         cURL 解析与执行
- json_tools   JSONPath 提取
- xmind        XMind 转换 / 生成
- cron         Cron 表达式生成与解析
- geocode      地址转经纬度 / 经纬度转地址
"""
from fastapi import APIRouter

from api.v1.endpoints.tools_routers import (
    cron,
    curl,
    geocode,
    json_tools,
    text_tools,
    xmind,
)

router = APIRouter(prefix="/tools", tags=["工具箱"])
router.include_router(text_tools.router)
router.include_router(curl.router)
router.include_router(json_tools.router)
router.include_router(xmind.router)
router.include_router(cron.router)
router.include_router(geocode.router)

# 兼容重导出：历史上部分模块/测试直接从本模块导入这些名称，拆分后保持可用
from core.response import UnifiedException  # noqa: E402,F401
from api.v1.endpoints.tools_routers.text_tools import (  # noqa: E402,F401
    IdCardRequest,
    generate_id_card,
)
