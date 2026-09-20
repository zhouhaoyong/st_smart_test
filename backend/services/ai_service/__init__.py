"""Shared AI call pipeline — reuse across application modules.

Each module provides its own prompt and validation; this layer handles
provider lookup, LLM call, JSON parsing, and audit logging.

AI 调用日志写入策略：
- 每次实际发出的模型请求都写入调用记录。
- 服务商在模型执行前明确拒绝且未返回内容时不扣次数；响应已开始后发生异常、解析或校验失败时计入实际消费。

本包由原单文件 services/ai_service.py 拆分而来（纯代码搬家，未改任何对外行为）：
`from services.ai_service import <原任意公共名>` 全部仍然可用。

拆分边界：
- json_repair.py —— LLM 非法 JSON 修复 / 解析兜底。
- audit_quota.py —— 调用审计文案 / 用量归一化的纯函数。
- _shared.py —— 公共 import / 常量 / 类型 / 小工具。
- __init__.py（本文件）—— 门面重导出 + 真正写库/编排的运行时集群。

为什么写库/编排集群留在门面而非独立 orchestrator 子模块：
测试通过 `from services import ai_service` 后 `monkeypatch.setattr(ai_service, "<名>", ...)`
对**本包命名空间**里的 `AsyncSessionLocal`/`AiUsageLog`/`log_operation`/
`get_candidate_models_for_feature`/`get_provider_for_model`/`_ensure_ai_quota_available_immediate`/
`_log_ai_usage_immediate`/`_call_ai_for_feature` 打桩。这些被打桩且被同集群其它函数以裸名调用的
名字，必须与调用方处于同一命名空间（即本包 __init__ 的模块字典）打桩才会生效；若下沉到子模块，
调用方读取的是子模块字典，感知不到门面上的补丁。故整个运行时集群保留在本文件。
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json  # noqa: F401 - 保留门面命名空间与原单文件一致
import logging  # noqa: F401 - 保留门面命名空间与原单文件一致
import re  # noqa: F401 - 保留门面命名空间与原单文件一致
import uuid
from collections.abc import Awaitable, Callable  # noqa: F401 - 保留门面命名空间一致
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.response import UnifiedException
from db.session import AsyncSessionLocal
from models.ai_models import AiUsageLog
from models.models_workbench import (
    TWCompletedRequirement,
    TWMergedRequirement,
    TWProject,
    TWRequirement,
    TWVersion,
)
from services.ai_model_service import get_candidate_models_for_feature, get_provider_for_model, model_required_message
from utils.audit_logger import build_project_audit_description, log_operation

from ._shared import (
    AiConcurrencyBusyError,
    AiStreamCallback,
    _AiResponseValidationError,
    _ai_call_stage_name,
    _emit_ai_stream_event,
    _normalize_call_group_id,
    _retry_candidate_payload,
    _with_call_meta,
    logger,
)
from .json_repair import (
    _aggressive_quote_escape,
    _insert_missing_commas,
    _json_repair,
    _parse_json,
    _parse_json_with_log,
    _repair_at_position,
    _repair_chinese_string_terminators,
    _repair_json,
    _repair_missing_json_values,
    _robust_json_parse,
)
from .audit_quota import (
    _detailed_model_failure_reason,
    extract_provider_request_id,
    _extract_model_error_message,
    _summarize_model_attempt_error,
    _usage_audit_operation,
    combine_usage,
    mask_provider_credentials,
    summarize_usage,
)


def _is_pre_execution_provider_rejection(message: str) -> bool:
    """识别模型执行前就被服务商明确拒绝的错误。"""
    text = str(message or "").strip().lower()
    if any(marker in text for marker in (
        "insufficient_quota", "insufficient quota", "insufficient balance",
        "balance exhausted", "余额不足", "额度不足", "余额或额度不足",
        "rate limit", "too many requests", "限流", "请求过于频繁",
        "鉴权失败", "认证失败", "接口不存在",
    )):
        return True
    return bool(re.search(r"\b(?:http\s*)?(?:400|401|402|403|404|429)\b", text))


def _model_call_consumed_on_failure(
    message: str,
    *,
    call_attempted: bool,
    response_observed: bool,
) -> bool:
    """判断失败调用是否应计入消费；无法确认时按已发起调用保守计数。"""
    if not call_attempted:
        return False
    if response_observed:
        return True
    return not _is_pre_execution_provider_rejection(message)


async def _get_retry_candidates(current_user, candidates: list, used_model_id: int | None) -> list[dict[str, Any]]:
    """列出尚可调用的候选模型，不实际请求模型，也不自动重试。"""
    from services.ai_quota_service import check_model_ai_quota

    retry_candidates: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as quota_db:
        for candidate in candidates:
            if getattr(candidate, "id", None) == used_model_id:
                continue
            try:
                allowed, used, limit, _message, quota_scope = await check_model_ai_quota(
                    quota_db, current_user, candidate,
                )
                if not allowed:
                    continue
            except Exception:
                continue
            remaining = max(0, limit - used) if limit is not None and limit > 0 else limit
            retry_candidates.append(_retry_candidate_payload(
                candidate,
                quota_used=used,
                quota_limit=limit,
                quota_remaining=remaining,
                quota_scope=quota_scope,
            ))
    return retry_candidates


async def _used_model_quota_snapshot(
    current_user,
    model_id: int | None,
    quota_scope: str | None,
) -> dict[str, Any] | None:
    """返回本次实际调用模型的「调用后」额度快照，供前端用量条展示。

    在独立会话中重新统计，确保能读到本轮刚落库的调用记录（今日已用含本次）。
    - scope：platform / personal / superuser（超管不限）
    - limit：-1 表示不限，None 表示未配置，其余为日额度
    - used / remaining：今日已用、今日剩余（不限/未配置时可能为 None）
    统计失败时返回 None，业务侧不因额度展示失败而中断。
    """
    if not current_user or not model_id:
        return None
    scope = quota_scope or "platform"
    if scope == "superuser" or (scope == "platform" and bool(getattr(current_user, "is_superuser", False))):
        return {"scope": "superuser", "used": None, "limit": -1, "remaining": None}
    try:
        from services.ai_quota_service import (
            get_user_model_quota_info,
            get_user_platform_quota_info,
        )

        async with AsyncSessionLocal() as quota_db:
            if scope == "personal":
                info = await get_user_model_quota_info(quota_db, current_user.id, model_id)
            else:
                info = await get_user_platform_quota_info(quota_db, current_user.id)
        return {
            "scope": "personal" if scope == "personal" else "platform",
            "used": info.get("today_used"),
            "limit": info.get("daily_limit"),
            "remaining": info.get("remaining"),
        }
    except Exception:
        return None


async def _log_ai_usage_immediate(
    user_id: int | None,
    user_name: str | None,
    action: str,
    model: str | None,
    target_type: str,
    target_id: int,
    tokens_estimated: int | None,
    model_id: int | None,
    *,
    feature: str | None = None,
    status: str = "succeeded",
    failure_reason: str | None = None,
    quota_consumed: bool = True,
    quota_scope: str | None = None,
    call_group_id: str | None = None,
    usage_summary: dict[str, Any] | None = None,
    provider_request_id: str | None = None,
    audit_project_name: str | None = None,
) -> None:
    """Write AiUsageLog in a SEPARATE session, flushed immediately.

    This ensures token consumption is recorded even if the main
    transaction rolls back because of parse/validation errors.
    """
    try:
        details = usage_summary if isinstance(usage_summary, dict) else {}

        def _usage_token(name: str) -> int | None:
            value = details.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            return int(value)

        async with AsyncSessionLocal() as s:
            s.add(AiUsageLog(
                user_id=user_id,
                action=action,
                model=model,
                target_type=target_type,
                target_id=target_id,
                tokens_estimated=tokens_estimated or 1,
                input_tokens=_usage_token("input_tokens"),
                output_tokens=_usage_token("output_tokens"),
                cache_tokens=_usage_token("cache_tokens"),
                total_tokens=_usage_token("total_tokens"),
                provider_request_id=str(provider_request_id).strip()[:120] if provider_request_id else None,
                model_id=model_id,
                feature=feature,
                status=status,
                failure_reason=failure_reason,
                quota_consumed=quota_consumed,
                quota_count=1 if quota_consumed else 0,
                quota_scope=quota_scope,
                call_group_id=call_group_id,
            ))
            if user_id is not None:
                operation = _usage_audit_operation(status)
                project_name = await _resolve_ai_project_name(
                    s,
                    target_type=target_type,
                    target_id=target_id,
                    explicit_project_name=audit_project_name,
                )
                description = f"{_ai_call_stage_name(action, feature or '')}：{operation}"
                if project_name:
                    description = build_project_audit_description(project_name, description)
                await log_operation(
                    db=s,
                    user_id=user_id,
                    user_name=user_name or f"用户 #{user_id}",
                    module="ai_call",
                    operation=operation,
                    target_id=target_id or None,
                    target_name=model or "未确定模型",
                    description=description,
                )
            await s.commit()
    except Exception:
        pass  # 日志写入失败不影响主流程


async def _resolve_ai_project_name(
    db: AsyncSession,
    *,
    target_type: str,
    target_id: int | None,
    explicit_project_name: str | None = None,
) -> str | None:
    """解析工作台 AI 调用所属项目；解析失败不影响用量和审计落库。"""
    if explicit_project_name and str(explicit_project_name).strip():
        return str(explicit_project_name).strip()
    if not target_id or not target_type.startswith("tw_"):
        return None
    try:
        if target_type == "tw_project":
            result = await db.execute(
                select(TWProject.name).where(TWProject.id == target_id, TWProject.is_deleted == False)
            )
            return result.scalar_one_or_none()
        model_map = {
            "tw_version": TWVersion,
            "tw_requirement": TWRequirement,
            "tw_completed_requirement": TWCompletedRequirement,
            "tw_merged_requirement": TWMergedRequirement,
        }
        model = model_map.get(target_type)
        if model is None:
            return None
        scope_result = await db.execute(
            select(model.project_id).where(model.id == target_id, model.is_deleted == False)
        )
        project_id = scope_result.scalar_one_or_none()
        if not project_id:
            return None
        project_result = await db.execute(
            select(TWProject.name).where(TWProject.id == project_id, TWProject.is_deleted == False)
        )
        return project_result.scalar_one_or_none()
    except Exception:
        return None


async def _ensure_ai_quota_available_immediate(current_user, model) -> str:
    """在真实调用前按最终路由模型检查对应额度。"""
    if not current_user or not getattr(current_user, "id", None):
        return "system"
    try:
        from services.ai_quota_service import check_model_ai_quota

        async with AsyncSessionLocal() as s:
            allowed, _used, _limit, message, quota_scope = await check_model_ai_quota(s, current_user, model)
            if not allowed:
                raise UnifiedException(code=429, message=message or "今日 AI 配额已用完")
            return quota_scope
    except UnifiedException:
        raise
    except Exception as exc:
        logger.warning("AI 配额检查失败，拒绝执行本次调用: %s", exc)
        raise UnifiedException(code=500, message="AI 额度检查失败，请稍后重试")


@asynccontextmanager
async def _ai_user_concurrency_guard(current_user):
    """Reject concurrent AI calls from the same user across app workers."""
    user_id = getattr(current_user, "id", None)
    if not user_id:
        yield
        return
    lock_name = f"smart_test_ai_user_{int(user_id)}"
    guard_db = AsyncSessionLocal()
    if not hasattr(guard_db, "execute"):
        # 允许纯单元测试替换数据库会话；真实 AsyncSession 始终支持 execute。
        yield
        return
    acquired = False
    try:
        result = await guard_db.execute(
            text("SELECT GET_LOCK(:lock_name, 0)"), {"lock_name": lock_name},
        )
        acquired = result.scalar() == 1
        if not acquired:
            raise AiConcurrencyBusyError("当前已有 AI 请求正在处理中，请等待本次请求结束后再试")
        yield
    finally:
        if acquired:
            try:
                await guard_db.execute(
                    text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": lock_name},
                )
            except Exception:
                logger.warning("释放 AI 用户并发锁失败: %s", lock_name, exc_info=True)
        await guard_db.close()


def _is_platform_ai_model(model) -> bool:
    return (getattr(model, "scope", "platform") or "platform") != "personal"


@asynccontextmanager
async def _ai_model_concurrency_guard(current_user, model):
    """Limit platform-model calls across users and application workers.

    Personal models intentionally bypass both locks. Platform requests use one
    MySQL connection to hold the per-user lock and one of the shared slots for
    the duration of the provider call.
    """
    if not _is_platform_ai_model(model):
        yield
        return

    user_id = getattr(current_user, "id", None)
    guard_db = AsyncSessionLocal()
    if not hasattr(guard_db, "execute"):
        yield
        return

    user_lock_name = f"smart_test_ai_user_{int(user_id)}" if user_id else None
    acquired_user = False
    acquired_slot = None
    try:
        if user_lock_name:
            result = await guard_db.execute(
                text("SELECT GET_LOCK(:lock_name, 0)"), {"lock_name": user_lock_name},
            )
            acquired_user = result.scalar() == 1
            if not acquired_user:
                raise AiConcurrencyBusyError("当前已有 AI 请求正在处理中，请等待本次请求结束后再试")

        max_concurrent = max(1, int(getattr(settings, "AI_PLATFORM_MAX_CONCURRENT", 3)))
        for slot_index in range(max_concurrent):
            slot_name = f"smart_test_ai_platform_slot_{slot_index}"
            result = await guard_db.execute(
                text("SELECT GET_LOCK(:lock_name, 0)"), {"lock_name": slot_name},
            )
            if result.scalar() == 1:
                acquired_slot = slot_name
                break
        if acquired_slot is None:
            raise AiConcurrencyBusyError("当前平台模型请求较多，请稍后重试")

        yield
    finally:
        if acquired_slot:
            try:
                await guard_db.execute(
                    text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": acquired_slot},
                )
            except Exception:
                logger.warning("释放 AI 平台并发槽位失败: %s", acquired_slot, exc_info=True)
        if acquired_user:
            try:
                await guard_db.execute(
                    text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": user_lock_name},
                )
            except Exception:
                logger.warning("释放 AI 用户并发锁失败: %s", user_lock_name, exc_info=True)
        await guard_db.close()


async def _run_provider_call_with_concurrency(current_user, model, call):
    async with _ai_model_concurrency_guard(current_user, model):
        return await call()


async def _call_ai_for_feature(
    db: AsyncSession,
    current_user,
    *,
    feature: str,
    system_prompt: str,
    user_content: str,
    required_keys: list[str] | None = None,
    required_any_keys: list[str] | None = None,
    audit_action: str = "ai_call",
    target_type: str = "",
    target_id: int = 0,
    tokens_estimated: int | None = None,
    return_metadata: bool = False,
    max_tokens: int | None = None,
    raw_mode: bool = False,
    stream_callback: AiStreamCallback | None = None,
    allow_missing_required_keys: bool = False,
    selected_model_id: int | None = None,
    call_group_id: str | None = None,
    audit_project_name: str | None = None,
) -> dict:
    """Generic AI pipeline for any feature.

    1. Caller checks user quota
    2. Look up the provider/model for *feature*
    3. Call the LLM via `_chat(system_prompt, user_content)`
    4. **IMMEDIATELY log AiUsageLog** (tokens consumed the moment _chat returns)
    5. Parse the response as JSON (skip if raw_mode=True)
    6. Validate response structure before recording the final call result.

    Raises UnifiedException when the model is unavailable or the
    response is unusable.  Caller is responsible for quota checks.
    """
    call_id = f"{audit_action}-{uuid.uuid4().hex[:10]}"
    effective_call_group_id = _normalize_call_group_id(call_group_id) or call_id
    call_title = _ai_call_stage_name(audit_action, feature)
    call_meta = {
        "call_id": call_id,
        "call_group_id": effective_call_group_id,
        "call_title": call_title,
        "stage_name": call_title,
        "audit_action": audit_action,
        "feature": feature,
    }

    async def _log_rejected_call(message: str, candidate=None, rejected_quota_scope: str | None = None) -> None:
        await _log_ai_usage_immediate(
            user_id=getattr(current_user, "id", None),
            user_name=getattr(current_user, "real_name", None),
            action=audit_action,
            model=getattr(candidate, "model", None),
            model_id=getattr(candidate, "id", None),
            target_type=target_type,
            target_id=target_id,
            tokens_estimated=tokens_estimated,
            feature=feature,
            status="failed",
            failure_reason=message,
            quota_consumed=False,
            quota_scope=rejected_quota_scope,
            call_group_id=effective_call_group_id,
            audit_project_name=audit_project_name,
        )

    # 用独立短连接查询候选模型，查完立刻归还，不占用调用方(请求级)的 db 连接。
    # 原因：下面的 LLM 调用最长可达 600s，若沿用请求级连接查询，会把该连接一直钉在连接池之外；
    # 一旦客户端超时/断开导致请求被取消，get_db 的 close 来不及把连接归还，
    # 就会触发 “non-checked-in connection ... GC” 的连接泄漏告警。
    # 候选模型对象随后只读列字段（provider/base_url/model/billing_config 等），expunge 成游离态后仍可安全使用。
    async with AsyncSessionLocal() as _lookup_db:
        candidates = await get_candidate_models_for_feature(_lookup_db, feature, limit=50, current_user=current_user)
        for _candidate in candidates:
            _lookup_db.expunge(_candidate)
    if not candidates:
        message = model_required_message(feature)
        await _log_rejected_call(message)
        raise UnifiedException(code=400, message=message)
    # 单次请求只使用当前优先级最高的模型；失败由用户主动确认后重试，
    # 避免自动切换其他模型产生额外额度消耗。

    # 候选顺序固定为平台模型优先、同范围按 ID 升序；失败由用户主动选择后重试。
    model = None
    quota_scope = ""
    if selected_model_id is not None:
        try:
            normalized_selected_model_id = int(selected_model_id)
        except (TypeError, ValueError):
            message = "所选模型当前不可用，请重新选择"
            await _log_rejected_call(message)
            raise UnifiedException(code=400, message=message)
        model = next(
            (candidate for candidate in candidates if getattr(candidate, "id", None) == normalized_selected_model_id),
            None,
        )
        if model is None:
            # 候选列表已同时校验可见性、归属、启用状态和额度可用性。
            message = "所选模型当前不可用，请重新选择"
            await _log_rejected_call(message)
            raise UnifiedException(code=400, message=message)
        try:
            quota_scope = await _ensure_ai_quota_available_immediate(current_user, model)
        except UnifiedException as exc:
            model_scope = getattr(model, "scope", "platform") or "platform"
            scope_text = "平台模型" if model_scope == "platform" else "我的模型"
            model_name = str(getattr(model, "name", None) or getattr(model, "model", None) or "未命名模型")[:100]
            quota_message = str(exc.message or "今日额度已用完")
            user_message = f"{scope_text}「{model_name}」{quota_message}。"
            retry_candidates = await _get_retry_candidates(current_user, candidates, getattr(model, "id", None))
            platform_model_unavailable = model_scope == "platform"
            if platform_model_unavailable:
                if retry_candidates:
                    user_message += "请选择其他可用模型重试。"
                else:
                    user_message += "当前没有其他可用模型，请先在 AI 模型配置中完成模型配置后再试。"
            await _log_rejected_call(user_message, model, model_scope)
            raise UnifiedException(
                code=exc.code,
                message=user_message,
                data={
                    "quota_exhausted": True,
                    "current_model_scope": model_scope,
                    "current_model_name": model_name,
                    "retry_candidates": retry_candidates,
                    "platform_model_unavailable": platform_model_unavailable,
                    "call_group_id": effective_call_group_id,
                },
            ) from exc
    else:
        retry_candidates = await _get_retry_candidates(current_user, candidates, None)
        message = "请先明确选择本次使用的 AI 模型，系统不会自动切换模型。"
        await _log_rejected_call(message)
        raise UnifiedException(
            code=400,
            message=message,
            data={
                "retry_candidates": retry_candidates,
                "call_group_id": effective_call_group_id,
            },
        )
    request_models = [model]

    # 余额仅由配置人显式查询，不在每次模型调用后额外产生费用接口请求。
    billing: dict[str, Any] = {"enabled": False, "amount": None, "text": None}

    ai_error_message = None
    model_error = None
    model_response_observed = False
    model_call_attempted = False
    provider_request_id = None
    tried_models: list[str] = []
    model_attempts: list[dict[str, object]] = []
    call_deadline = asyncio.get_running_loop().time() + 600
    await _emit_ai_stream_event(stream_callback, _with_call_meta({
        "type": "call_start",
        "message": f"开始{call_title}",
    }, call_meta))
    await _emit_ai_stream_event(stream_callback, _with_call_meta({
        "type": "input",
        "input_text": f"【System】\n{system_prompt}\n\n【User】\n{user_content}",
        "feature": feature,
    }, call_meta))

    for index, candidate in enumerate(request_models, 1):
        model_name = candidate.name or candidate.model
        tried_models.append(model_name)
        attempt_info: dict[str, object] = {
            "sequence": index,
            "model_id": candidate.id,
            "model_name": model_name,
            "status": "running",
            "retry_count": 0,
        }
        model_attempts.append(attempt_info)
        await _emit_ai_stream_event(stream_callback, _with_call_meta({
            "type": "model_start",
            "model_id": candidate.id,
            "model_name": model_name,
            "sequence": index,
            "feature": feature,
        }, call_meta))
        try:
            provider = await get_provider_for_model(candidate)
            # 单次最大输出 tokens 解析：
            # - 调用方显式传入 max_tokens 时以其为准（如 compose 明确指定）
            # - 未传入(None)时，回落到该模型自身配置的 max_output_tokens
            # - 仍为空则保持 None（由 provider 决定是否发送该参数）
            effective_max_tokens = max_tokens
            if effective_max_tokens is None:
                effective_max_tokens = getattr(candidate, "max_output_tokens", None)
            remaining_timeout = max(1, call_deadline - asyncio.get_running_loop().time())
            # 纯模型耗时：从发起本次模型调用到流式/整体返回结束，供前端「本轮用量」展示。
            _call_started_at = asyncio.get_running_loop().time()
            async def _on_delta(delta: Any) -> None:
                if isinstance(delta, dict):
                    kind = str(delta.get("kind") or "output")
                    delta_text = str(delta.get("delta") or "")
                else:
                    kind = "output"
                    delta_text = str(delta or "")
                await _emit_ai_stream_event(stream_callback, _with_call_meta({
                    "type": "reasoning_delta" if kind == "reasoning" else "delta",
                    "delta": delta_text,
                    "model_id": candidate.id,
                    "model_name": model_name,
                    "sequence": index,
                    "feature": feature,
                }, call_meta))

            async def _on_response_observed() -> None:
                nonlocal model_response_observed
                model_response_observed = True

            # 非 raw 模式说明本次调用期望结构化 JSON：请求网关强制 JSON 模式（不支持则由 provider 自动降级）。
            want_json_mode = not raw_mode
            async def _invoke_provider():
                nonlocal model_call_attempted
                if stream_callback and hasattr(provider, "_chat_with_meta_stream"):
                    model_call_attempted = True
                    return await asyncio.wait_for(
                        provider._chat_with_meta_stream(
                            system_prompt,
                            user_content,
                            max_tokens=effective_max_tokens,
                            on_delta=_on_delta,
                            on_response_observed=_on_response_observed,
                            json_mode=want_json_mode,
                        ),
                        timeout=remaining_timeout,
                    )
                if hasattr(provider, "_chat_with_meta"):
                    model_call_attempted = True
                    return await asyncio.wait_for(
                        provider._chat_with_meta(
                            system_prompt,
                            user_content,
                            max_tokens=effective_max_tokens,
                            on_response_observed=_on_response_observed,
                            json_mode=want_json_mode,
                        ),
                        timeout=remaining_timeout,
                    )
                model_call_attempted = True
                return await asyncio.wait_for(
                    provider._chat(system_prompt, user_content, max_tokens=effective_max_tokens),
                    timeout=remaining_timeout,
                )

            chat_result = await _run_provider_call_with_concurrency(current_user, candidate, _invoke_provider)
            if isinstance(chat_result, dict):
                raw = str(chat_result.get("content") or "")
                usage = chat_result.get("usage") or {}
                finish_reason = chat_result.get("finish_reason")
                provider_request_id = (
                    chat_result.get("provider_request_id")
                    or extract_provider_request_id(chat_result.get("raw"))
                )
            else:
                raw = str(chat_result or "")
                usage = {}
                finish_reason = None
            model_elapsed_ms = int(max(0.0, asyncio.get_running_loop().time() - _call_started_at) * 1000)
            model = candidate
            ai_error_message = None
            attempt_info["status"] = "success"
            await _emit_ai_stream_event(stream_callback, _with_call_meta({
                "type": "model_success",
                "model_id": candidate.id,
                "model_name": model_name,
                "sequence": index,
                "feature": feature,
            }, call_meta))
            break
        except asyncio.CancelledError:
            # 取消发生在哪一步是确定可分的，别笼统写成「是否完成无法确认」：
            # 未发出请求时我们确知没消耗，只有请求已发出、响应还没回来那一段才真的无从判断。
            if not model_call_attempted:
                cancel_reason = "已被用户取消：请求尚未发给模型服务商，未消耗额度"
            elif model_response_observed:
                cancel_reason = "已被用户取消：模型已开始返回内容，已按消耗计入"
            else:
                cancel_reason = "已被用户取消：请求已发出但未收到响应，服务商是否计费无法确认，已按消耗计入"
            await _log_ai_usage_immediate(
                user_id=getattr(current_user, "id", None),
                user_name=getattr(current_user, "real_name", None),
                action=audit_action,
                model=getattr(candidate, "model", None),
                model_id=getattr(candidate, "id", None),
                target_type=target_type,
                target_id=target_id,
                tokens_estimated=tokens_estimated,
                feature=feature,
                status="failed",
                failure_reason=cancel_reason,
                quota_consumed=model_call_attempted,
                quota_scope=quota_scope,
                call_group_id=effective_call_group_id,
                audit_project_name=audit_project_name,
            )
            raise
        except AiConcurrencyBusyError as exc:
            # 并发守卫在调用模型之前就拒绝了本次请求：没发出请求、没消耗额度。
            # 因此不写失败调用记录、不做模型故障归类，原文抛给上层如实提示用户，
            # 避免被包装成「平台模型暂时无法使用」把人引去排查模型配置。
            busy_message = str(exc.message)
            attempt_info["status"] = "failed"
            attempt_info["error"] = busy_message
            await _emit_ai_stream_event(stream_callback, _with_call_meta({
                "type": "model_failed",
                "model_id": candidate.id,
                "model_name": model_name,
                "sequence": index,
                "feature": feature,
                "error": busy_message,
            }, call_meta))
            await _emit_ai_stream_event(stream_callback, _with_call_meta({
                "type": "call_failed",
                "message": busy_message,
                "failure_reason": busy_message,
                "billing": billing,
                "usage": {},
                "model_attempts": model_attempts,
                "retry_candidates": [],
                "platform_model_unavailable": False,
            }, call_meta))
            raise
        except Exception as exc:
            attempt_info["status"] = "failed"
            attempt_info["error"] = _summarize_model_attempt_error(str(exc))
            await _emit_ai_stream_event(stream_callback, _with_call_meta({
                "type": "model_failed",
                "model_id": candidate.id,
                "model_name": model_name,
                "sequence": index,
                "feature": feature,
                "error": attempt_info["error"],
            }, call_meta))
            msg = str(exc)
            model_error = _extract_model_error_message(msg)
            if isinstance(exc, TimeoutError) or "timeout" in msg.lower():
                ai_error_message = "AI模型响应超时，长时间未返回内容，请检查本地模型服务或稍后重试"
            elif "connect" in msg.lower() or "name or service not known" in msg.lower() or "unsupportedprotocol" in msg.lower():
                ai_error_message = "AI模型连接失败，请检查模型地址和网络"
            elif "401" in msg or "403" in msg or "unauthorized" in msg.lower():
                ai_error_message = "AI模型认证失败，请检查API Key"
            elif "404" in msg:
                ai_error_message = "AI模型接口不存在，请检查模型地址"
            else:
                ai_error_message = f"AI调用失败：{_summarize_model_attempt_error(msg)}"
            break

    if ai_error_message:
        failure_message = str(model_error or ai_error_message)
        quota_consumed = _model_call_consumed_on_failure(
            failure_message,
            call_attempted=model_call_attempted,
            response_observed=model_response_observed,
        )
        failure_reason = _detailed_model_failure_reason(failure_message)
        display_error = _detailed_model_failure_reason(failure_message)
        retry_candidates = await _get_retry_candidates(current_user, candidates, getattr(model, "id", None))
        platform_model_unavailable = (getattr(model, "scope", "platform") or "platform") == "platform"
        user_message = (
            f"平台模型暂时无法使用：{display_error}。请联系超管检查平台模型配置；"
            "如有其他可用模型，请在失败消息中选择模型重试。"
            if platform_model_unavailable else f"AI调用失败：{display_error}"
        )
        await _log_ai_usage_immediate(
            user_id=getattr(current_user, "id", None),
            user_name=getattr(current_user, "real_name", None),
            action=audit_action,
            model=getattr(model, "model", None),
            model_id=getattr(model, "id", None),
            target_type=target_type,
            target_id=target_id,
            tokens_estimated=tokens_estimated,
            feature=feature,
            status="failed",
            failure_reason=failure_reason,
            quota_consumed=quota_consumed,
            quota_scope=quota_scope,
            call_group_id=effective_call_group_id,
            audit_project_name=audit_project_name,
        )
        await _emit_ai_stream_event(stream_callback, _with_call_meta({
            "type": "call_failed",
            "message": user_message,
            "failure_reason": failure_reason,
            "billing": billing,
            "usage": locals().get("usage") or {},
            "model_attempts": model_attempts,
            "retry_candidates": retry_candidates,
            "platform_model_unavailable": platform_model_unavailable,
        }, call_meta))
        raise UnifiedException(
            code=400,
            message=user_message,
            data={
                "ai_cost": billing,
                "failure_reason": failure_reason,
                "model_attempts": model_attempts,
                "retry_candidates": retry_candidates,
                "platform_model_unavailable": platform_model_unavailable,
                "call_group_id": effective_call_group_id,
            },
        )

    estimated = tokens_estimated or max(1, (len(system_prompt) + len(user_content)) // 2)
    if usage.get("total_tokens"):
        estimated = int(usage.get("total_tokens") or estimated)

    metadata = {
        "model_id": model.id if model else None,
        "model": getattr(provider, "model", None),
        "usage": usage,
        "finish_reason": finish_reason,
        "billing": billing,
        "model_attempts": model_attempts,
        "call_group_id": effective_call_group_id,
        # 纯模型耗时（毫秒）：仅成功路径可得，供「本轮用量」展示；拿不到则为 None。
        "elapsed_ms": locals().get("model_elapsed_ms"),
        "quota_scope": quota_scope,
        "provider_request_id": provider_request_id,
    }

    async def _raise_response_validation_error(message: str) -> None:
        """模型已返回内容但业务结构不可用：计额度并以失败终态落库。"""
        retry_candidates = await _get_retry_candidates(current_user, candidates, getattr(model, "id", None))
        metadata["retry_candidates"] = retry_candidates
        await _emit_ai_stream_event(stream_callback, _with_call_meta({
            "type": "call_failed",
            "message": message,
            "failure_reason": "模型已返回内容，但结果解析或校验失败",
            "billing": billing,
            "usage": usage,
            "model_id": metadata["model_id"],
            "model_name": metadata["model"],
            "model_attempts": model_attempts,
            "retry_candidates": retry_candidates,
        }, call_meta))
        raise _AiResponseValidationError(
            message=message,
            metadata=metadata,
            data={
                "ai_cost": billing,
                "failure_reason": "模型已返回内容，但结果解析或校验失败",
                "model_attempts": model_attempts,
                "retry_candidates": retry_candidates,
                "call_group_id": effective_call_group_id,
            },
        )

    if raw_mode:
        await _emit_ai_stream_event(stream_callback, _with_call_meta({"type": "parse", "message": "模型输出完成，正在整理原始内容", "feature": feature}, call_meta))
        result = {"raw": raw}
    else:
        await _emit_ai_stream_event(stream_callback, _with_call_meta({"type": "parse", "message": "模型输出完成，正在解析结构化 JSON", "feature": feature}, call_meta))
        result = _parse_json(raw)

    if not raw_mode and required_keys:
        if "raw" in result:
            await _raise_response_validation_error("AI 返回内容无法解析为 JSON，请重试")
        missing = [k for k in required_keys if k not in result]
        if missing and not allow_missing_required_keys:
            raw_preview = raw[:500] if raw else ""
            raw_tail = raw[-500:] if raw and len(raw) > 500 else ""
            raw_len = len(raw) if raw else 0
            parsed_keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
            logger.error(
                "AI 返回缺少必要字段: %s, 已解析字段: %s, raw长度=%d, raw前500字符: %s, raw末500字符: %s",
                missing, parsed_keys, raw_len, raw_preview, raw_tail,
            )
            await _raise_response_validation_error(f"AI返回缺少必要字段: {', '.join(missing)}，请重试")

    if not raw_mode and required_any_keys:
        parsed_keys = set(result) if isinstance(result, dict) else set()
        if not parsed_keys.intersection(required_any_keys):
            await _raise_response_validation_error("AI 返回结构不符合预期，请重试")

    await _emit_ai_stream_event(stream_callback, _with_call_meta({
        "type": "call_complete",
        "message": f"{call_title}完成",
        "billing": billing,
        "usage": usage,
        "model_id": model.id if model else None,
        "model_name": getattr(provider, "model", None),
        "model_attempts": model_attempts,
    }, call_meta))
    if return_metadata:
        await _emit_ai_stream_event(stream_callback, _with_call_meta({"type": "complete", "message": "AI 调用完成", "feature": feature}, call_meta))
        return result, metadata
    await _emit_ai_stream_event(stream_callback, _with_call_meta({"type": "complete", "message": "AI 调用完成", "feature": feature}, call_meta))
    return result


async def _call_ai_for_feature_with_logging(db: AsyncSession, current_user, **kwargs) -> dict:
    """统一执行一次模型请求并写调用记录；不会在服务端自动改用其他模型。"""
    expects_metadata = bool(kwargs.pop("return_metadata", False))
    try:
        result, metadata = await _call_ai_for_feature(
            db,
            current_user,
            return_metadata=True,
            **kwargs,
        )
    except _AiResponseValidationError as exc:
        metadata = exc.metadata
        await _log_ai_usage_immediate(
            user_id=getattr(current_user, "id", None),
            user_name=getattr(current_user, "real_name", None),
            action=str(kwargs.get("audit_action") or "ai_call"),
            model=metadata.get("model"),
            target_type=str(kwargs.get("target_type") or ""),
            target_id=int(kwargs.get("target_id") or 0),
            tokens_estimated=int((metadata.get("usage") or {}).get("total_tokens") or 1),
            model_id=metadata.get("model_id"),
            feature=str(kwargs.get("feature") or "") or None,
            status="failed",
            failure_reason="模型已返回内容，但结果解析或校验失败",
            quota_consumed=True,
            quota_scope=metadata.get("quota_scope"),
            call_group_id=metadata.get("call_group_id"),
            usage_summary=summarize_usage(metadata),
            provider_request_id=metadata.get("provider_request_id"),
            audit_project_name=kwargs.get("audit_project_name"),
        )
        raise

    await _log_ai_usage_immediate(
        user_id=getattr(current_user, "id", None),
        user_name=getattr(current_user, "real_name", None),
        action=str(kwargs.get("audit_action") or "ai_call"),
        model=metadata.get("model"),
        target_type=str(kwargs.get("target_type") or ""),
        target_id=int(kwargs.get("target_id") or 0),
        tokens_estimated=int((metadata.get("usage") or {}).get("total_tokens") or 1),
        model_id=metadata.get("model_id"),
        feature=str(kwargs.get("feature") or "") or None,
        quota_scope=metadata.get("quota_scope"),
        call_group_id=metadata.get("call_group_id"),
        usage_summary=summarize_usage(metadata),
        provider_request_id=metadata.get("provider_request_id"),
        audit_project_name=kwargs.get("audit_project_name"),
    )
    # 落库后再统计所用模型的「调用后」额度快照，确保今日已用含本次；失败降级为 None。
    metadata["model_quota"] = await _used_model_quota_snapshot(
        current_user,
        metadata.get("model_id"),
        metadata.get("quota_scope"),
    )
    if expects_metadata:
        return result, metadata
    return result


async def call_ai_for_feature(db: AsyncSession, current_user, **kwargs) -> dict:
    """Execute one AI call; concurrency is enforced after model selection."""
    return await _call_ai_for_feature_with_logging(db, current_user, **kwargs)
