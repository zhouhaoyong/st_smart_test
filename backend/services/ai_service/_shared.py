"""ai_service 拆分后的公共层：共享 import / 常量 / 类型 / 小工具。

本模块由原单文件 services/ai_service.py 拆分而来，负责公共依赖与 AI 功能命名归一。
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from core.response import UnifiedException

# 保持与原单文件一致的 logger 名称 "services.ai_service"，避免拆分后日志归属发生变化。
logger = logging.getLogger("services.ai_service")

_AI_FEATURE_LABELS = {
    "test_workbench_requirement_completion": "AI需求补全",
    "test_workbench_requirement_merge": "AI需求合并",
    "test_workbench_test_case_generate": "AI生成测试用例",
    "api_interface_case_generate": "接口批量生成用例",
}

_AI_CALL_STAGE_FEATURES = {
    "tw_requirement_refinement": "test_workbench_requirement_completion",
    "tw_requirement_compose": "test_workbench_requirement_completion",
    "tw_requirement_compose_continue": "test_workbench_requirement_completion",
    "tw_requirement_result_comparison": "test_workbench_requirement_completion",
    "tw_requirement_structure": "test_workbench_requirement_completion",
    "tw_requirement_merge_refinement": "test_workbench_requirement_merge",
    "tw_requirement_merge_compose": "test_workbench_requirement_merge",
    "tw_requirement_merge_compose_continue": "test_workbench_requirement_merge",
    "tw_requirement_merge_result_comparison": "test_workbench_requirement_merge",
    "tw_requirement_merge_preview": "test_workbench_requirement_merge",
    "tw_test_case_preflight": "test_workbench_test_case_generate",
    "tw_test_case_generate": "test_workbench_test_case_generate",
    "ui_generate_cases": "test_workbench_test_case_generate",
    "api_interface_case_generate": "api_interface_case_generate",
}

_LEGACY_AI_ACTION_LABELS = {
    "analyze": "历史动作：智能分析",
    "reanalyze": "历史动作：重新分析",
    "translate": "历史动作：翻译",
    "ui_analyze_requirement": "历史动作：需求分析",
    "ui_analyze_requirement_coverage_repair": "历史动作：需求覆盖率修复",
    "ui_generate_cases_coverage_repair": "历史动作：用例覆盖率修复",
    "ui_generate_script_set": "历史动作：脚本集生成",
    "ui_repair_script_set": "历史动作：脚本集修复",
    "ui_generate_cases_json_repair": "历史动作：用例 JSON 修复",
}

AiStreamCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class AiConcurrencyBusyError(UnifiedException):
    """并发守卫的前置拒绝：同一用户已有 AI 请求在跑，或平台模型并发槽位已满。

    这类拒绝发生在真正调用模型之前，既没消耗额度也不代表模型有问题，
    必须原样透传给调用方，不能落进「模型调用失败」分支被包装成
    「平台模型暂时无法使用」——那会把用户引去排查模型配置。
    """

    def __init__(self, message: str):
        super().__init__(code=429, message=message, data={"ai_concurrency_busy": True})


class _AiResponseValidationError(UnifiedException):
    """模型已返回内容，但后续结构化解析或校验失败。"""

    def __init__(self, *, message: str, metadata: dict[str, Any], data: dict[str, Any] | None = None):
        super().__init__(code=400, message=message, data=data)
        self.metadata = metadata


async def _emit_ai_stream_event(callback: AiStreamCallback | None, event: dict[str, Any]) -> None:
    if not callback:
        return
    result = callback(event)
    if result is not None:
        await result


def _ai_call_stage_name(audit_action: str, feature: str) -> str:
    feature_key = str(feature or "").strip()
    if feature_key in _AI_FEATURE_LABELS:
        return _AI_FEATURE_LABELS[feature_key]
    mapped_feature = _AI_CALL_STAGE_FEATURES.get(str(audit_action or "").strip())
    if mapped_feature:
        return _AI_FEATURE_LABELS[mapped_feature]
    legacy_label = _LEGACY_AI_ACTION_LABELS.get(str(audit_action or "").strip())
    if legacy_label:
        return legacy_label
    return "AI模型调用"


def _with_call_meta(event: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    merged = dict(event)
    merged.update(meta)
    return merged


def _normalize_call_group_id(value: str | None) -> str:
    """调用分组仅用于关联同一次用户主动操作，避免将任意长文本写入日志列。"""
    return str(value or "").strip()[:100]


def _retry_candidate_payload(
    model,
    *,
    quota_used: int | None = None,
    quota_limit: int | None = None,
    quota_remaining: int | None = None,
    quota_scope: str | None = None,
) -> dict[str, Any]:
    """失败后仅返回当前用户已可见的基础模型信息，不泄露配置。"""
    return {
        "id": model.id,
        "name": str(getattr(model, "name", None) or getattr(model, "model", "模型"))[:100],
        "model": str(getattr(model, "model", ""))[:100],
        "scope": getattr(model, "scope", "platform") or "platform",
        "connectivity_status": getattr(model, "connectivity_status", "unknown"),
        "reasoning_status": getattr(model, "reasoning_status", "unknown"),
        "usage_status": getattr(model, "usage_status", "unknown"),
        "quota_used": quota_used,
        "quota_limit": quota_limit,
        "quota_remaining": quota_remaining,
        "quota_scope": quota_scope,
    }
