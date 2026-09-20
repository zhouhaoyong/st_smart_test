"""测试工作台接口聚合入口。

各资源域的具体实现拆分在 test_workbench_routers 子包中：
- structure    项目 / 系统 / 版本 / 看板
- requirements 单条需求及 AI 追问、整理成文
- merged       合并需求
- test_cases   测试用例与执行记录
- bugs         Bug 记录与流转
- legacy       遗留项
"""
from fastapi import APIRouter

from api.v1.endpoints.test_workbench_routers import (
    bugs,
    legacy,
    merged,
    merged_ai,
    requirements,
    structure,
    test_cases,
)

router = APIRouter()
router.include_router(structure.router)
router.include_router(requirements.router)
router.include_router(merged.router)
router.include_router(merged_ai.router)
router.include_router(test_cases.router)
router.include_router(bugs.router)
router.include_router(legacy.router)
