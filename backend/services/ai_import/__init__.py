"""API 测试接口列表 AI 生成用例服务包。

- preview_store: 按会话设计的临时预览存储（归属 / 容量 / 过期 / 按时间淘汰）。
- summary:       接口明细提取、敏感信息脱敏、AI 结果归一、param_overrides 契约映射。

用例生成 / 事务保存复用现有统一 AI 能力与执行契约，
预览内容落到业务数据库，不复用旧的进程内解析缓存 _parse_cache。
"""
from services.ai_import.preview_store import (
    preview_store,
    PreviewExpiredError,
    PreviewNotFoundError,
    PreviewForbiddenError,
)
from services.ai_import.summary import (
    detail_for_generate,
    merge_generated_cases,
    apply_case_changes,
    build_system_generated_case,
    cases_by_temp_id,
    case_request_signature,
    build_param_overrides,
    assertion_for_case_type,
    DEFAULT_ASSERTION,
    PARAM_OVERRIDE_KEYS,
)

__all__ = [
    "preview_store",
    "PreviewExpiredError",
    "PreviewNotFoundError",
    "PreviewForbiddenError",
    "detail_for_generate",
    "merge_generated_cases",
    "apply_case_changes",
    "build_system_generated_case",
    "cases_by_temp_id",
    "case_request_signature",
    "build_param_overrides",
    "assertion_for_case_type",
    "DEFAULT_ASSERTION",
    "PARAM_OVERRIDE_KEYS",
]
