"""AI Models & Quota — API endpoints.

Shared AI infrastructure: model management, usage tracking, quota control.
"""
import logging
from types import SimpleNamespace
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response, error_response
from core.permissions import PERMISSION_DENIED_MESSAGE
from db.session import get_db
from core.security import get_current_active_user
from models.models import User
from models.ai_models import AiModel, AiModelDetectionLog, AiUsageLog, AiUserModelQuota
from llm.providers import OpenAICompatProvider
from schemas.ai_schemas import (
    AiModelCreate, AiModelUpdate, AiModelRead, AiModelFetchRequest,
    AiModelConnectivityRequest, AiModelBillingTestRequest,
    AiPlatformQuotaSettingRequest, AiModelQuotaRequest,
)
from services.ai_model_service import (
    list_models, query_models_page, has_enabled_platform_model,
    get_model, create_model, update_model, delete_model,
    get_candidate_models_for_feature, get_routable_models_for_feature, query_model_balance, resolve_model_api_key, mask_model_api_key,
    model_supports_reasoning, _reset_model_detection,
)
from services.ai_service import _ai_model_concurrency_guard
from services.ai_capability_service import (
    _mask_base_url,
    _probe_model_capabilities,
    _capability_result_payload,
    _capability_error_detail,
    capability_upstream_detail,
    CapabilityTestCancelled,
)
from services.ai_billing_service import (
    fetch_billing_balance,
    normalize_balance_query_config,
    test_billing_config,
)
from services.ai_quota_service import (
    check_model_ai_quota,
    check_user_ai_quota, get_platform_model_usage,
    get_platform_quota_setting, get_usage_summary, get_user_quota,
    get_user_model_quota_info, get_users_platform_quota_info, get_user_usage_quota_stats,
    list_users_with_quota_info, set_platform_quota_setting, set_user_model_quota, get_configured_quota_limit, get_valid_quota_limit,
    soft_delete_usage_logs,
)
from utils.audit_logger import log_operation, log_user_operation
from utils.oss_client import resolve_file_url
from core.timezone import beijing_now

logger = logging.getLogger(__name__)

router = APIRouter()


class UsageLogIdsRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)


class UsageLogFilterDeleteRequest(BaseModel):
    user_name: str | None = None
    phone: str | None = None
    keyword: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    model: str | None = None
    model_scope: str | None = None
    action: str | None = None
    result: str | None = None
    department: int | None = None
    caller_type: str | None = None
    model_owner_scope: str | None = None


# ---- Helpers ----

def _is_admin(user: User) -> bool:
    return user.is_manager or user.is_superuser


def _is_superadmin(user: User) -> bool:
    return user.is_superuser


def _check_admin(user: User):
    if not _is_admin(user):
        raise UnifiedException(code=403, message=PERMISSION_DENIED_MESSAGE)


def _check_superadmin(user: User):
    if not _is_superadmin(user):
        raise UnifiedException(code=403, message=PERMISSION_DENIED_MESSAGE)


def _can_view_all_ai_data(user: User) -> bool:
    return user.is_superuser


def _resolve_usage_user_id(user: User, scope: str) -> int | None:
    """超管可切换本人/全员，其他角色无论传入什么都只能查本人。"""
    return None if _can_view_all_ai_data(user) and scope != "self" else user.id


def _model_owner_id(model: AiModel) -> int | None:
    return getattr(model, "owner_user_id", None) or getattr(model, "created_by", None)


def _is_model_owner(user: User, model: AiModel) -> bool:
    return _model_owner_id(model) == user.id


def _can_manage_model(user: User, model: AiModel) -> bool:
    scope = getattr(model, "scope", "platform") or "platform"
    return _is_model_owner(user, model) or (_is_superadmin(user) and scope == "platform")


def _can_view_model(user: User, model: AiModel) -> bool:
    scope = getattr(model, "scope", "platform") or "platform"
    if scope == "platform":
        return bool(getattr(model, "enabled", False)) or _can_manage_model(user, model) or _is_superadmin(user)
    return _is_model_owner(user, model) or _is_superadmin(user)


def _model_read_payload(
    model: AiModel,
    user: User,
    creator_name: str,
    owner_name: str = "",
    platform_quota: dict | None = None,
    *,
    creator_avatar: str | None = None,
    owner_avatar: str | None = None,
) -> dict:
    owner = _is_model_owner(user, model)
    manager = _can_manage_model(user, model)
    super_readonly = _is_superadmin(user)
    expose_connection = manager or super_readonly
    balance_config = getattr(model, "balance_query_config", None)
    balance_visible = True
    return {
        "id": model.id, "name": model.name, "provider": model.provider, "model": model.model,
        "scope": getattr(model, "scope", "platform"), "owner_user_id": _model_owner_id(model),
        "creator_name": creator_name, "owner_name": owner_name,
        "creator_avatar": creator_avatar, "owner_avatar": owner_avatar,
        "platform_quota": platform_quota,
        "enabled": model.enabled,
        "invalidated_reason": getattr(model, "invalidated_reason", None),
        "connectivity_status": getattr(model, "connectivity_status", "unknown"),
        "connectivity_checked_at": getattr(model, "connectivity_checked_at", None),
        "reasoning_status": getattr(model, "reasoning_status", "unknown"),
        "reasoning_checked_at": getattr(model, "reasoning_checked_at", None),
        "usage_status": getattr(model, "usage_status", "unknown"),
        "usage_checked_at": getattr(model, "usage_checked_at", None),
        "max_output_tokens": getattr(model, "max_output_tokens", None) if expose_connection else None,
        # 列表接口一律不返回接口地址；编辑回显 / 查看详情走 GET /models/{id}。
        "base_url": None,
        "has_api_key": bool(model.api_key_encrypted) if manager else False,
        "api_key_masked": mask_model_api_key(model) if manager else None,
        # List responses never include URLs, headers or balance values. Users
        # with management permission load configuration from protected endpoints.
        "balance_query_configured": bool(isinstance(balance_config, dict) and balance_config.get("url")) if balance_visible else None,
        "balance_query_enabled": bool(getattr(model, "balance_query_enabled", False)),
        "balance_query_status": getattr(model, "balance_query_status", "unknown") if balance_visible else None,
        "balance_query_checked_at": getattr(model, "balance_query_checked_at", None) if balance_visible else None,
        "can_edit": manager,
        "can_test": manager,
        "can_query_balance": bool(
            owner
            and
            getattr(model, "balance_query_enabled", False)
            and isinstance(balance_config, dict)
            and balance_config.get("url")
        ),
        "created_at": model.created_at, "updated_at": model.updated_at,
    }


def _normalize_balance_query_update(data: dict) -> dict:
    if "balance_query_config" not in data:
        return data
    config = normalize_balance_query_config(data.get("balance_query_config"))
    if data.get("balance_query_enabled") and not config.get("url"):
        raise ValueError("请先填写余额接口后再启用余额查询")
    data["balance_query_config"] = config
    return data


def _mask_key(key: str | None) -> str:
    if not key or len(key) <= 8:
        return key or ""
    return key[:4] + "****" + key[-4:]


# ---- Usage & Quota ----

@router.get("/usage/quota")
async def api_quota_info(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Return today's quota info for the current user."""
    try:
        platform_quota_setting = await get_platform_quota_setting(db)
        configured_platform_limit = get_configured_quota_limit(platform_quota_setting.daily_limit if platform_quota_setting else None)
        daily_limit = -1 if _is_superadmin(current_user) else configured_platform_limit
        today_used = await get_platform_model_usage(db, current_user.id)
        personal_model_result = await db.execute(
            select(AiModel.id)
            .join(AiUserModelQuota, AiUserModelQuota.model_id == AiModel.id)
            .where(
                AiModel.scope == "personal",
                or_(
                    AiModel.owner_user_id == current_user.id,
                    (AiModel.owner_user_id.is_(None) & (AiModel.created_by == current_user.id)),
                ),
                AiModel.enabled.is_(True),
                AiModel.invalidated_reason.is_(None),
                AiModel.is_deleted.is_(False),
                AiUserModelQuota.user_id == current_user.id,
                AiUserModelQuota.is_deleted.is_(False),
                AiUserModelQuota.daily_limit > 0,
            )
            .limit(1)
        )
        has_personal_model_access = personal_model_result.scalar_one_or_none() is not None
        return success_response(data={
            "quota": daily_limit,
            "today_used": today_used,
            "remaining": max(0, daily_limit - today_used) if daily_limit is not None and daily_limit >= 0 else (-1 if _is_superadmin(current_user) else None),
            "has_access": _is_superadmin(current_user) or (daily_limit is not None and daily_limit > 0) or has_personal_model_access,
            "has_personal_model_access": has_personal_model_access,
            "platform_quota_setting": configured_platform_limit,
        })
    except Exception as exc:
        logger.exception("Failed to load quota info")
        return error_response(code=500, message="AI额度查询失败，请稍后重试")


@router.get("/quotas/platform-setting")
async def api_get_platform_quota_setting(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """所有用户可查看平台模型额度；配置仅由超管修改。"""
    try:
        setting = await get_platform_quota_setting(db)
        return success_response(data={"daily_limit": get_configured_quota_limit(setting.daily_limit if setting else None)})
    except Exception:
        logger.exception("Failed to load platform quota setting")
        return error_response(code=500, message="平台模型额度查询失败，请稍后重试")


@router.put("/quotas/platform-setting")
async def api_set_platform_quota_setting(
    data: AiPlatformQuotaSettingRequest,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    _check_superadmin(current_user)
    setting = await set_platform_quota_setting(db, data.daily_limit, current_user.id)
    await db.commit()
    await log_operation(
        db=db, user_id=current_user.id, user_name=current_user.real_name,
        module="ai_quota", operation="设置平台模型额度", target_id=setting.id,
        target_name="平台模型额度", description=f"设置非超管用户平台模型日额度：{setting.daily_limit} 次",
    )
    await db.commit()
    return success_response(data={"daily_limit": setting.daily_limit}, message="平台模型额度已更新")


@router.get("/usage/logs")
async def api_usage_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="all"),
    user_name: str | None = Query(default=None),
    phone: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    model: str | None = Query(default=None),
    model_scope: str | None = Query(default=None),
    model_owner_scope: str | None = Query(default=None),
    action: str | None = Query(default=None),
    result: str | None = Query(default=None),
    department: int | None = Query(default=None),
    caller_type: str | None = Query(default=None),
    include_stats: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询 AI 用量记录；超级管理员可查看全部，管理员和普通用户仅查看本人。"""
    try:
        from services.ai_quota_service import normalize_usage_filters

        is_super = _is_superadmin(current_user)
        can_view_all = _can_view_all_ai_data(current_user)
        target_user_id = _resolve_usage_user_id(current_user, scope)
        filters = normalize_usage_filters(
            user_name=user_name,
            phone=phone,
            keyword=keyword,
            model=model,
            model_scope=model_scope,
            action=action,
            result=result,
            department=department,
            caller_type=caller_type,
            start_time=start_time,
            end_time=end_time,
            model_owner_id=current_user.id if model_owner_scope == "self" else None,
        )
        result = await get_usage_summary(
            db,
            user_id=target_user_id,
            page=page, page_size=page_size,
            include_stats=include_stats,
            filters=filters,
        )
        result["is_superadmin"] = is_super
        result["is_manager"] = bool(current_user.is_manager)
        result["can_view_all"] = can_view_all
        result["scope"] = "self" if target_user_id is not None else "all"
    except Exception:
        logger.exception("Failed to load usage logs")
        return error_response(code=500, message="AI用量查询失败，请稍后重试")
    return success_response(data=result)


@router.get("/usage/user-quota-stats")
async def api_user_quota_stats(
    user_id: int | None = Query(default=None),
    mode: str = Query(default="today"),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """用量统计弹窗：按用户 + 时间维度返回平台模型 / 我的模型用量。

    非超管仅能查看本人；超管可查看指定用户。mode=today 返回额度视角
    （已用 / 上限 / 剩余），其余按时间段仅返回次数。
    """
    try:
        from services.ai_quota_service import _parse_usage_time

        can_view_all = _can_view_all_ai_data(current_user)
        target_user_id = user_id if (can_view_all and user_id) else current_user.id
        data = await get_user_usage_quota_stats(
            db,
            target_user_id,
            start_time=_parse_usage_time(start_time),
            end_time=_parse_usage_time(end_time),
            today_mode=(mode == "today"),
        )
    except Exception:
        logger.exception("Failed to load user quota stats")
        return error_response(code=500, message="用量统计查询失败，请稍后重试")
    return success_response(data=data)


@router.post("/usage/logs/delete-batch")
async def api_delete_usage_logs_batch(
    data: UsageLogIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """超管批量软删除已选调用记录。"""
    _check_superadmin(current_user)
    deleted_count = await soft_delete_usage_logs(db, ids=data.ids)
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="ai_usage",
        operation="调用记录清理",
        description=f"删除调用记录 {deleted_count} 条",
    )
    return success_response(data={"deleted_count": deleted_count}, message=f"已删除 {deleted_count} 条调用记录")


@router.post("/usage/logs/delete-all")
async def api_delete_usage_logs_all(
    data: UsageLogFilterDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """超管按当前筛选条件软删除全部调用记录。"""
    _check_superadmin(current_user)
    from services.ai_quota_service import normalize_usage_filters

    filters = normalize_usage_filters(
        user_name=data.user_name,
        phone=data.phone,
        keyword=data.keyword,
        model=data.model,
        model_scope=data.model_scope,
        action=data.action,
        result=data.result,
        department=data.department,
        caller_type=data.caller_type,
        start_time=data.start_time,
        end_time=data.end_time,
        model_owner_id=current_user.id if data.model_owner_scope == "self" else None,
    )
    deleted_count = await soft_delete_usage_logs(db, filters=filters)
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="ai_usage",
        operation="调用记录清理",
        description=f"删除调用记录 {deleted_count} 条",
    )
    return success_response(data={"deleted_count": deleted_count}, message=f"已删除 {deleted_count} 条调用记录")


# ---- Models ----

@router.get("/models")
async def api_list_models(
    tab: str = Query(default="mine"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    model_name: str | None = Query(default=None),
    model_identifier: str | None = Query(default=None),
    enabled: str | None = Query(default=None),
    connectivity_status: str | None = Query(default=None),
    creator_name: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """按页签分页查询模型：mine 我的模型 / platform 平台模型 / users 用户模型（仅超管）。"""
    if tab not in {"mine", "platform", "users"}:
        tab = "mine"
    is_super = _is_superadmin(current_user)
    # 用户模型仅超管可见：非超管一律拒绝，不返回他人模型数据。
    if tab == "users" and not is_super:
        return error_response(code=403, message=PERMISSION_DENIED_MESSAGE)

    models, total = await query_models_page(
        db,
        tab=tab,
        current_user_id=current_user.id,
        is_superuser=is_super,
        model_name=model_name,
        model_identifier=model_identifier,
        enabled=enabled,
        connectivity_status=connectivity_status,
        creator_name=creator_name,
        page=page,
        page_size=page_size,
    )

    creator_ids = {m.created_by for m in models if m.created_by}
    owner_ids = {_model_owner_id(m) for m in models if _model_owner_id(m)}
    user_ids = creator_ids | owner_ids
    if user_ids:
        user_rows = await db.execute(select(User.id, User.real_name, User.avatar).where(User.id.in_(user_ids)))
        user_map = {uid: {"name": name, "avatar": resolve_file_url(avatar)} for uid, name, avatar in user_rows.all()}
    else:
        user_map = {}
    personal_owner_ids = {
        int(_model_owner_id(m))
        for m in models
        if getattr(m, "scope", "platform") == "personal" and _model_owner_id(m)
    }
    platform_quota_map = await get_users_platform_quota_info(db, personal_owner_ids)

    items = []
    for m in models:
        owner_id = _model_owner_id(m)
        items.append(_model_read_payload(
            m,
            current_user,
            user_map.get(m.created_by, {}).get("name", ""),
            user_map.get(owner_id, {}).get("name", ""),
            platform_quota_map.get(owner_id) if getattr(m, "scope", "platform") == "personal" else None,
            creator_avatar=user_map.get(m.created_by, {}).get("avatar"),
            owner_avatar=user_map.get(owner_id, {}).get("avatar"),
        ))
    return success_response(data={
        "items": items,
        "total": total,
        "has_available_platform_model": await has_enabled_platform_model(db),
    })


@router.get("/models/for-feature")
async def api_models_for_feature(
    feature: str = Query(...),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the models that would be used for a given AI feature, in priority order."""
    candidates = await get_routable_models_for_feature(db, feature, limit=limit, current_user=current_user)
    result = []
    for m in candidates:
        _, quota_used, quota_limit, _, quota_scope = await check_model_ai_quota(db, current_user, m)
        quota_remaining = max(0, quota_limit - quota_used) if quota_limit > 0 else -1
        result.append({
            "id": m.id,
            "name": m.name,
            "model": m.model,
            "scope": getattr(m, "scope", "platform"),
            "enabled": m.enabled,
            "supports_reasoning": model_supports_reasoning(m),
            "connectivity_status": getattr(m, "connectivity_status", "unknown"),
            "reasoning_status": getattr(m, "reasoning_status", "unknown"),
            "usage_status": getattr(m, "usage_status", "unknown"),
            "quota_used": quota_used,
            "quota_limit": quota_limit,
            "quota_remaining": quota_remaining,
            "quota_scope": quota_scope,
        })
    return success_response(data={"candidates": result, "total": len(result)})


@router.post("/models")
async def api_create_model(data: AiModelCreate, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_active_user)):
    data_dict = data.model_dump()
    try:
        _normalize_balance_query_update(data_dict)
    except ValueError as exc:
        return error_response(code=400, message=str(exc))
    requested_scope = data_dict.get("scope") or ("platform" if _is_superadmin(current_user) else "personal")
    if requested_scope not in {"platform", "personal"}:
        return error_response(code=400, message="模型范围不正确")
    if requested_scope == "platform":
        _check_superadmin(current_user)
    data_dict["scope"] = requested_scope
    data_dict["created_by"] = current_user.id
    data_dict["owner_user_id"] = current_user.id
    model = await create_model(db, data_dict)
    await db.commit()
    await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                        module="ai_model", operation="创建", target_id=model.id,
                        target_name=model.name, description=f"创建AI模型：{model.name}")
    return success_response(data={"id": model.id, "name": model.name})


@router.put("/models/{model_id}")
async def api_update_model(model_id: int, data: AiModelUpdate, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_active_user)):
    model = await get_model(db, model_id)
    if not model:
        return error_response(code=404, message="模型不存在")
    if not _can_manage_model(current_user, model):
        return error_response(code=403, message="权限不足")
    update_data = data.model_dump(exclude_unset=True)
    if not _is_model_owner(current_user, model):
        update_data.pop("balance_query_enabled", None)
        update_data.pop("balance_query_config", None)
        update_data.pop("billing_enabled", None)
        update_data.pop("billing_config", None)
    try:
        _normalize_balance_query_update(update_data)
    except ValueError as exc:
        return error_response(code=400, message=str(exc))
    if "scope" in update_data and update_data["scope"] != getattr(model, "scope", "platform"):
        return error_response(code=400, message="模型范围创建后不可修改")
    previous_enabled = bool(model.enabled)
    # 失效模型恢复启用：仍须满足当前权限；能力检测仅用于展示配置状态。
    # 平台模型额外要求当前仍是超管（防止降级后的用户重新拉起面向全平台的平台模型）。
    if update_data.get("enabled") and getattr(model, "invalidated_reason", None):
        if getattr(model, "scope", "platform") == "platform" and not _is_superadmin(current_user):
            return error_response(code=400, message="当前模型已因权限变化失效")
        model.invalidated_reason = None
    updated = await update_model(db, model, update_data)
    await db.commit()
    enabled_changed = "enabled" in update_data and bool(updated.enabled) != previous_enabled
    operation = "更新"
    if enabled_changed:
        operation = "启用" if updated.enabled else "停用"
    await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                        module="ai_model", operation=operation, target_id=updated.id,
                        target_name=updated.name, description=f"{operation}AI模型：{updated.name}",
                        details={"enabled": bool(updated.enabled), "previous_enabled": previous_enabled})
    await db.commit()
    return success_response(data={"id": updated.id, "name": updated.name})


@router.get("/models/{model_id}")
async def api_get_model_detail(model_id: int, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_active_user)):
    """模型详情（含接口地址）。模型使用人和超级管理员查看时返回完整接口地址；无权者 403。

    仅用于编辑回显 / 查看详情，列表接口不再返回接口地址。
    """
    model = await get_model(db, model_id)
    if not model:
        return error_response(code=404, message="模型不存在")
    if not _can_view_model(current_user, model):
        return error_response(code=403, message="权限不足")
    owner = _is_model_owner(current_user, model)
    manager = _can_manage_model(current_user, model)
    creator_name = ""
    owner_name = ""
    owner_id = _model_owner_id(model)
    if model.created_by or owner_id:
        user_rows = await db.execute(select(User.id, User.real_name, User.avatar).where(User.id.in_({uid for uid in (model.created_by, owner_id) if uid})))
        user_map = {uid: {"name": name, "avatar": resolve_file_url(avatar)} for uid, name, avatar in user_rows.all()}
        creator_info = user_map.get(model.created_by, {})
        owner_info = user_map.get(owner_id, {})
        creator_name = creator_info.get("name", "")
        owner_name = owner_info.get("name", "")
        creator_avatar = creator_info.get("avatar")
        owner_avatar = owner_info.get("avatar")
    else:
        creator_avatar = None
        owner_avatar = None
    platform_quota = None
    personal_quota = None
    if getattr(model, "scope", "platform") == "personal" and owner_id:
        platform_quota = (await get_users_platform_quota_info(db, {int(owner_id)})).get(int(owner_id))
        personal_quota = await get_user_model_quota_info(db, int(owner_id), model.id)
    payload = _model_read_payload(
        model,
        current_user,
        creator_name,
        owner_name,
        platform_quota,
        creator_avatar=creator_avatar,
        owner_avatar=owner_avatar,
    )
    # 详情接口对模型所有者和超管返回完整接口地址，其他可查看者返回脱敏地址。
    if manager or _is_superadmin(current_user):
        payload["base_url"] = model.base_url
        payload["max_output_tokens"] = getattr(model, "max_output_tokens", None)
    else:
        payload["base_url"] = _mask_base_url(model.base_url)
    payload["personal_quota"] = personal_quota
    return success_response(data=payload)


@router.get("/models/{model_id}/balance-query-config")
async def api_get_model_balance_query_config(model_id: int, db: AsyncSession = Depends(get_db),
                                             current_user: User = Depends(get_current_active_user)):
    """Return raw balance-query configuration to users with model management permission."""
    model = await get_model(db, model_id)
    if not model:
        return error_response(code=404, message="模型不存在")
    if not _is_model_owner(current_user, model):
        return error_response(code=403, message=PERMISSION_DENIED_MESSAGE)
    try:
        config = normalize_balance_query_config(getattr(model, "balance_query_config", None))
    except ValueError:
        return error_response(code=400, message="余额查询配置格式不正确，请重新配置")
    return success_response(data={
        "configured": bool(config.get("url")),
        "enabled": bool(getattr(model, "balance_query_enabled", False)),
        "config": config,
    })


@router.post("/models/test-billing")
async def api_test_model_billing_draft(data: AiModelBillingTestRequest,
                                       db: AsyncSession = Depends(get_db),
                                       current_user: User = Depends(get_current_active_user)):
    """测试未保存模型的余额接口，不创建模型记录。"""
    base_url = (data.base_url or "").strip()
    model_name = (data.model or "").strip()
    if not base_url or "://" not in base_url:
        return error_response(code=400, message="接口地址无效")
    if not model_name:
        return error_response(code=400, message="模型名称不能为空")
    try:
        billing_config = normalize_balance_query_config(data.balance_query_config)
    except ValueError as exc:
        return error_response(code=400, message=str(exc))
    if not billing_config.get("url"):
        return error_response(code=400, message="请先填写余额接口")
    probe = SimpleNamespace(
        id=0,
        name="未保存模型",
        provider=data.provider,
        base_url=base_url,
        model=model_name,
        api_key_encrypted=None,
        enabled=True,
        show_cost=False,
        billing_enabled=True,
        billing_config=billing_config,
        balance_query_config=billing_config,
        created_by=current_user.id,
    )
    try:
        result = await test_billing_config(probe, billing_config, api_key_override=data.api_key or None)
        if not result.get("supported"):
            await log_user_operation(
                db=db,
                user=current_user,
                module="ai_model",
                operation="测试余额接口",
                target_name=model_name,
                description=f"未保存模型余额接口测试失败：{model_name}",
                details={"status": "failed"},
            )
            return error_response(code=400, message=result.get("message") or "余额接口不可用", data=result)
        await log_user_operation(
            db=db,
            user=current_user,
            module="ai_model",
            operation="测试余额接口",
            target_name=model_name,
            description=f"未保存模型余额接口测试成功：{model_name}",
            details={"status": "success"},
        )
        return success_response(data=result, message="余额接口可用")
    except Exception as exc:
        logger.warning("Draft balance query test failed: %s", exc)
        await log_user_operation(
            db=db,
            user=current_user,
            module="ai_model",
            operation="测试余额接口",
            target_name=model_name or "未保存模型",
            description=f"未保存模型余额接口测试失败：{model_name or '未保存模型'}",
            details={"status": "failed"},
        )
        return error_response(code=400, message="余额接口测试失败，请检查配置和授权")


@router.post("/models/{model_id}/test-billing")
async def api_test_model_billing(model_id: int, data: AiModelUpdate, db: AsyncSession = Depends(get_db),
                                 current_user: User = Depends(get_current_active_user)):
    model = await get_model(db, model_id)
    if not model:
        return error_response(code=404, message="模型不存在")
    if not _is_model_owner(current_user, model):
        return error_response(code=403, message=PERMISSION_DENIED_MESSAGE)
    try:
        billing_config = normalize_balance_query_config(data.balance_query_config or data.billing_config)
    except ValueError as exc:
        return error_response(code=400, message=str(exc))
    if not billing_config.get("url"):
        return error_response(code=400, message="请先填写余额接口")
    # 允许从请求中传入 api_key 覆盖（新建模型时 model 尚未保存 api_key）
    api_key_override = data.api_key or None
    try:
        result = await test_billing_config(model, billing_config, api_key_override=api_key_override)
        if not result.get("supported"):
            await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                                module="ai_model", operation="测试余额接口", target_id=model.id,
                                target_name=model.name, description=f"余额接口测试失败：{model.name}")
            return error_response(code=400, message=result.get("message") or "计费接口不可用", data=result)
        await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                            module="ai_model", operation="测试余额接口", target_id=model.id,
                            target_name=model.name, description=f"余额接口测试成功：{model.name}")
        return success_response(data=result, message="余额接口可用")
    except Exception as exc:
        logger.error("Balance query config test failed for model %s: %s", model_id, exc)
        await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                            module="ai_model", operation="测试余额接口", target_id=model.id,
                            target_name=model.name, description=f"余额接口测试失败：{model.name}")
        return error_response(code=400, message="余额接口测试失败，请检查配置和授权")


@router.post("/models/{model_id}/check-balance")
async def api_check_model_balance(model_id: int, data: AiModelUpdate = None,
                                   db: AsyncSession = Depends(get_db),
                                   current_user: User = Depends(get_current_active_user)):
    """按模型配置查询余额；仅模型创建者在余额配置已启用且测试通过时可查询。"""
    model = await get_model(db, model_id)
    if not model:
        return error_response(code=404, message="模型不存在")
    if not _can_view_model(current_user, model):
        return error_response(code=403, message=PERMISSION_DENIED_MESSAGE)
    if not _is_model_owner(current_user, model):
        return error_response(code=403, message=PERMISSION_DENIED_MESSAGE)

    try:
        config = getattr(model, "balance_query_config", None) or getattr(model, "billing_config", None) or {}
        if not config or not config.get("url"):
            return error_response(code=400, message="请先配置余额查询接口")
        if not getattr(model, "balance_query_enabled", False):
            return error_response(code=400, message="余额查询尚未启用")
        result = await fetch_billing_balance(model, config)
        balance = result.get("balance")
        if balance is None:
            raise ValueError("余额接口未返回可识别的余额字段")
        model.balance_query_status = "passed"
        model.balance_query_checked_at = beijing_now()
        await db.commit()
        await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                            module="ai_model", operation="查询余额", target_id=model.id,
                            target_name=model.name, description=f"查询模型余额成功：{model.name}")
        await db.commit()
        return success_response(data={"balance": balance, "available": result.get("available")}, message="余额查询完成")
    except Exception as exc:
        model.balance_query_status = "failed"
        model.balance_query_checked_at = beijing_now()
        await db.commit()
        logger.warning("Balance query failed for model %s: %s", model_id, exc)
        await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                            module="ai_model", operation="查询余额", target_id=model.id,
                            target_name=model.name, description=f"查询模型余额失败：{model.name}")
        message = str(exc) if isinstance(exc, ValueError) else "余额查询失败，请检查余额接口配置和服务商授权"
        return error_response(code=400, message=message)


def _model_list_urls(base_url: str) -> list[str]:
    """保留非标准中转的根路径兼容，同时支持 OpenAI 兼容的 /v1/models。"""
    normalized_url = base_url.rstrip("/")
    urls = [f"{normalized_url}/models"]
    if not normalized_url.endswith("/v1"):
        urls.append(f"{normalized_url}/v1/models")
    return urls


@router.post("/models/fetch-models")
async def api_fetch_models(data: AiModelFetchRequest, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_active_user)):
    """查询模型列表，兼容根路径和 OpenAI 兼容的 /v1/models。"""
    base_url = data.base_url
    api_key = data.api_key
    # 未指定已保存模型时不编造操作对象，避免出现「拉取模型列表成功：模型列表」这类冗余文案。
    target_model_name: str | None = None

    def audit_suffix() -> str:
        return f"：{target_model_name}" if target_model_name else ""

    async def audit_fetch(operation: str, description: str) -> None:
        await log_operation(
            db=db, user_id=current_user.id, user_name=current_user.real_name,
            module="ai_model", operation=operation, target_id=data.model_id or None,
            target_name=target_model_name or "模型服务", description=description,
        )
        await db.commit()

    if data.model_id and (not api_key or not base_url):
        model = await get_model(db, data.model_id)
        if model:
            if not _can_manage_model(current_user, model):
                return error_response(code=403, message="权限不足")
            if not base_url:
                base_url = model.base_url
            if not api_key and model.api_key_encrypted:
                api_key = resolve_model_api_key(model)
            target_model_name = model.name

    base_url = (base_url or "").rstrip("/")
    if not base_url or "://" not in base_url:
        return error_response(code=400, message="接口地址无效")
    if not api_key:
        return error_response(code=400, message="请先配置 API Key")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            last_status = None
            for models_url in _model_list_urls(base_url):
                try:
                    resp = await client.get(
                        models_url,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    last_status = exc.response.status_code if exc.response is not None else None
                    logger.info("Fetch models HTTP %s from %s", last_status or "?", models_url)
                    continue

                try:
                    body = resp.json()
                except ValueError:
                    logger.info("Fetch models returned non-JSON data from %s", models_url)
                    continue
                models = body.get("data") if isinstance(body, dict) else None
                if not isinstance(models, list):
                    logger.info("Fetch models returned no data list from %s", models_url)
                    continue
                ids = [model["id"] for model in models if isinstance(model, dict) and model.get("id")]
                await audit_fetch("拉取模型列表", f"拉取模型列表成功{audit_suffix()}，共 {len(ids)} 个模型")
                return success_response(data={"models": ids})
        if last_status is not None:
            await audit_fetch("拉取模型列表", f"拉取模型列表失败{audit_suffix()}（HTTP {last_status}）")
            return error_response(code=400, message=f"查询失败 (HTTP {last_status})")
        await audit_fetch("拉取模型列表", f"拉取模型列表失败{audit_suffix()}")
        return error_response(code=400, message="未获取到模型列表，请检查接口地址或确认服务支持 /v1/models")
    except Exception as exc:
        logger.error("Fetch models error for %s: %s", base_url, exc)
        await audit_fetch("拉取模型列表", f"拉取模型列表失败{audit_suffix()}")
        return error_response(code=400, message="查询模型列表异常，请检查网络和接口地址")


@router.delete("/models/{model_id}")
async def api_delete_model(model_id: int, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_active_user)):
    model = await get_model(db, model_id)
    if not model:
        return error_response(code=404, message="模型不存在")
    if not _can_manage_model(current_user, model):
        return error_response(code=403, message="权限不足")
    await delete_model(db, model)
    await db.commit()
    await log_operation(db=db, user_id=current_user.id, user_name=current_user.real_name,
                        module="ai_model", operation="删除", target_id=model.id,
                        target_name=model.name, description=f"删除AI模型：{model.name}")
    await db.commit()
    return success_response(message="已删除")


@router.put("/quotas/models/{model_id}")
async def api_set_personal_model_quota(
    model_id: int,
    data: AiModelQuotaRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    model = await get_model(db, model_id)
    if not model or getattr(model, "scope", "platform") != "personal":
        return error_response(code=400, message="我的模型不存在")
    if not _is_model_owner(current_user, model):
        return error_response(code=403, message="权限不足")
    quota = await set_user_model_quota(db, current_user.id, model.id, data.daily_limit)
    await db.commit()
    await log_operation(
        db=db, user_id=current_user.id, user_name=current_user.real_name,
        module="ai_quota", operation="设置我的模型额度", target_id=model.id, target_name=model.name,
        description=f"设置我的模型每日额度：{quota.daily_limit} 次",
    )
    await db.commit()
    return success_response(data={"model_id": model.id, "daily_limit": quota.daily_limit})


@router.get("/quotas/models")
async def api_list_personal_model_quotas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """我的模型额度：本人可管理，超管可查看全部成员模型。"""
    models = [
        model for model in await list_models(db)
        if getattr(model, "scope", "platform") == "personal"
        and (_is_model_owner(current_user, model) or _is_superadmin(current_user))
    ]
    if not models:
        return success_response(data=[])
    model_ids = [model.id for model in models]
    owner_ids = {_model_owner_id(model) for model in models if _model_owner_id(model) is not None}
    owner_rows = await db.execute(select(User.id, User.real_name, User.avatar).where(User.id.in_(owner_ids)))
    owner_info = {
        user_id: {"name": real_name, "avatar": resolve_file_url(avatar)}
        for user_id, real_name, avatar in owner_rows.all()
    }
    quota_rows = await db.execute(select(AiUserModelQuota).where(
        AiUserModelQuota.model_id.in_(model_ids),
        AiUserModelQuota.is_deleted.is_(False),
    ))
    quota_map = {
        (item.user_id, item.model_id): get_valid_quota_limit(item.daily_limit)
        for item in quota_rows.scalars().all()
    }
    today = beijing_now().replace(hour=0, minute=0, second=0, microsecond=0)
    usage_rows = await db.execute(
        select(AiUsageLog.user_id, AiUsageLog.model_id, func.count(AiUsageLog.id))
        .where(
            AiUsageLog.model_id.in_(model_ids),
            AiUsageLog.quota_consumed == True,
            AiUsageLog.is_deleted.is_(False),
            AiUsageLog.created_at >= today,
        )
        .group_by(AiUsageLog.user_id, AiUsageLog.model_id)
    )
    usage_map = {(user_id, model_id): count for user_id, model_id, count in usage_rows.all()}
    return success_response(data=[{
        "model_id": model.id,
        "model_name": model.name,
        "owner_user_id": _model_owner_id(model),
        "owner_name": owner_info.get(_model_owner_id(model), {}).get("name", ""),
        "owner_avatar": owner_info.get(_model_owner_id(model), {}).get("avatar"),
        "daily_limit": quota_map.get((_model_owner_id(model), model.id)),
        "today_used": usage_map.get((_model_owner_id(model), model.id), 0),
        "can_edit": _is_model_owner(current_user, model),
    } for model in models])


@router.post("/models/{model_id}/test-capabilities")
async def api_test_model_capabilities(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    request: Request = None,
):
    """模型能力检测（三合一）：一次真实调用同时判定连通性 / 思考模式 / 用量统计并落库（编辑：读库配置）。"""
    model = await get_model(db, model_id)
    if not model:
        return error_response(code=404, message="模型不存在")
    if not _can_manage_model(current_user, model):
        return error_response(code=403, message="权限不足")

    api_key = resolve_model_api_key(model) or ""
    provider_type = getattr(model, "provider", "openai-compat")
    # 仅已保存模型的检测允许写回状态；草稿检测接口只返回结果，避免污染已有模型。
    persist_connectivity_result = True

    async def is_cancelled():
        return request is not None and await request.is_disconnected()

    try:
        probe_provider = OpenAICompatProvider(
            api_key=api_key,
            base_url=model.base_url,
            model=model.model,
            wire_api=provider_type,
            enable_thinking=model_supports_reasoning(model),
            thinking_profile=getattr(model, "reasoning_profile", "chat_template"),
        )
        async with _ai_model_concurrency_guard(current_user, model):
            result = await _probe_model_capabilities(
                model.base_url, api_key, model.model, provider_type,
                cancel_check=is_cancelled,
                provider=probe_provider,
            )
        if await is_cancelled():
            raise CapabilityTestCancelled
        now = beijing_now()
        if persist_connectivity_result:
            # 探针跑通 => 连通通过；未等完整流拿到用量时保持 unknown，避免误判为不支持。
            model.connectivity_status = "passed"
            model.connectivity_checked_at = now
            model.reasoning_status = "supported" if result["supported"] else "unsupported"
            model.reasoning_profile = result["profile"]
            model.reasoning_checked_at = now
            model.usage_status = result.get("usage_status", "unknown")
            model.usage_checked_at = now if model.usage_status == "supported" else None
        db.add(AiModelDetectionLog(
            model_id=model.id,
            operator_user_id=current_user.id,
            connectivity_status="passed",
            reasoning_status=model.reasoning_status,
            usage_status=model.usage_status,
            message="能力检测通过",
        ))
        await db.commit()
        await log_operation(
            db=db, user_id=current_user.id, user_name=current_user.real_name,
            module="ai_model", operation="模型能力检测", target_id=model.id, target_name=model.name,
            description=f"模型能力检测通过：{model.name}",
            # 三项检测结论放入详情，操作内容只保留一句可读摘要。
            details={
                "status": "success",
                "connectivity": "通过",
                "reasoning": "可展示" if result["supported"] else "未检出",
                "usage": "可统计" if result.get("usage_status") == "supported" else "未检测",
            },
        )
        await db.commit()
        return success_response(data=_capability_result_payload(result), message="能力检测完成")
    except CapabilityTestCancelled:
        _reset_model_detection(model)
        await db.commit()
        return error_response(code=400, message="能力检测已终止")
    except UnifiedException:
        raise
    except Exception as exc:
        # 浏览器已经不等这次结果了（用户终止 / 前端等待超时）：中断由前端单独上报，
        # 这里再写一条失败，同一次检测就会留下两条日志，故只重置状态、不记失败。
        if await is_cancelled():
            _reset_model_detection(model)
            await db.commit()
            return error_response(code=400, message="能力检测已终止")
        # 探针整体失败视为连通失败：连通失败下思考/用量无从谈起，一并回到未检测。
        model.connectivity_status = "failed"
        model.connectivity_checked_at = beijing_now()
        model.reasoning_status = "unknown"
        model.reasoning_checked_at = beijing_now()
        model.usage_status = "unknown"
        model.usage_checked_at = beijing_now()
        detail = _capability_error_detail(exc)
        provider_error = capability_upstream_detail(exc)
        db.add(AiModelDetectionLog(
            model_id=model.id,
            operator_user_id=current_user.id,
            connectivity_status="failed",
            reasoning_status="unknown",
            usage_status="unknown",
            # 记录已脱敏的服务商返回，便于事后按检测历史回溯上游原因。
            message=f"能力检测失败：{detail}" + (f"｜服务商返回：{provider_error}" if provider_error else ""),
        ))
        await db.commit()
        logger.error("Model capability test failed for %s: %r", model_id, exc)
        await log_operation(
            db=db, user_id=current_user.id, user_name=current_user.real_name,
            module="ai_model", operation="模型能力检测", target_id=model.id, target_name=model.name,
            description=f"模型能力检测失败：{model.name}",
            details={"status": "failed", "reason": detail},
        )
        await db.commit()
        return error_response(
            code=400,
            message=f"能力检测失败：{detail}",
            data={"provider_error": provider_error} if provider_error else None,
        )


@router.post("/models/{model_id}/reset-capabilities")
async def api_reset_model_capabilities(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    reason: str = Query("manual", description="manual=用户手动终止；timeout=前端等待超时中断"),
):
    """终止能力检测后，把已保存模型的三项检测状态重置为未检测。

    中断原因只有前端知道（用户点终止 / 浏览器等到超时），因此由前端上报，
    后端据此区分审计文案，避免把两种性质不同的中断混为一谈。
    """
    model = await get_model(db, model_id)
    if not model:
        return error_response(code=404, message="模型不存在")
    if not _can_manage_model(current_user, model):
        return error_response(code=403, message="权限不足")
    _reset_model_detection(model)
    await db.commit()
    interrupted = reason == "timeout"
    await log_operation(
        db=db, user_id=current_user.id, user_name=current_user.real_name,
        module="ai_model",
        operation="模型能力检测",
        target_id=model.id, target_name=model.name,
        description=(
            f"模型能力检测中断：{model.name}" if interrupted
            else f"模型能力检测终止：{model.name}"
        ),
        details={"status": "interrupted", "reason": "前端等待超时"} if interrupted else None,
    )
    await db.commit()
    return success_response(data={"id": model.id}, message="能力检测已终止")


@router.post("/models/test-capabilities")
async def api_test_model_capabilities_draft(
    data: AiModelConnectivityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    request: Request = None,
):
    """新建(未保存)时的模型能力检测：仅用请求体配置发探针，不落库；结果由前端暂存，随「保存」一并落库。
    与已保存模型的 /models/{id}/test-capabilities 共用同一探测逻辑，保证新建/编辑行为一致。"""
    base_url = (data.base_url or "").rstrip("/")
    api_key = (data.api_key or "").strip()
    model_name = (data.model or "").strip()
    provider_type = data.provider
    if not base_url or "://" not in base_url:
        return error_response(code=400, message="接口地址无效")
    if not model_name:
        return error_response(code=400, message="模型名称不能为空")

    if data.model_id:
        saved_model = await get_model(db, data.model_id)
        if not saved_model:
            return error_response(code=404, message="模型不存在")
        if not _can_manage_model(current_user, saved_model):
            return error_response(code=403, message="权限不足")
        if not api_key:
            api_key = resolve_model_api_key(saved_model) or ""

    async def is_cancelled():
        return request is not None and await request.is_disconnected()

    try:
        probe_provider = OpenAICompatProvider(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            wire_api=provider_type,
        )
        async with _ai_model_concurrency_guard(current_user, data):
            result = await _probe_model_capabilities(
                base_url, api_key, model_name, provider_type,
                cancel_check=is_cancelled,
                provider=probe_provider,
            )
        if await is_cancelled():
            raise CapabilityTestCancelled
        await log_operation(
            db=db, user_id=current_user.id, user_name=current_user.real_name,
            # 新建未保存与已保存模型统一记为「模型能力检测」，不再区分草稿态。
            module="ai_model", operation="模型能力检测", target_name=model_name,
            description=f"模型能力检测通过：{model_name}",
            details={
                "status": "success",
                "connectivity": "通过",
                "reasoning": "可展示" if result["supported"] else "未检出",
                "usage": "可统计" if result.get("usage_status") == "supported" else "未检测",
            },
        )
        await db.commit()
        return success_response(data=_capability_result_payload(result), message="能力检测完成")
    except CapabilityTestCancelled:
        return error_response(code=400, message="能力检测已终止")
    except UnifiedException:
        raise
    except Exception as exc:
        # 与已保存模型一致：浏览器已经不等了就不再记失败，避免和前端上报的中断重复。
        if await is_cancelled():
            return error_response(code=400, message="能力检测已终止")
        detail = _capability_error_detail(exc)
        provider_error = capability_upstream_detail(exc)
        logger.error("Draft model capability test failed: %r", exc)
        await log_operation(
            db=db, user_id=current_user.id, user_name=current_user.real_name,
            module="ai_model", operation="模型能力检测", target_name=model_name or "未命名模型",
            description=f"模型能力检测失败：{model_name or '未命名模型'}",
            details={"status": "failed", "reason": detail},
        )
        await db.commit()
        return error_response(
            code=400,
            message=f"能力检测失败：{detail}",
            data={"provider_error": provider_error} if provider_error else None,
        )


# ---- Quota Management ----

@router.get("/quotas/users")
async def api_list_quota_users(
    q: str = Query(default=""),
    q_name: str = Query(default=""),
    q_phone: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List paginated active users with their quota info. Only superadmin can view all."""
    _check_superadmin(current_user)
    items, total = await list_users_with_quota_info(
        db,
        keyword=q.strip() or None,
        name_keyword=q_name.strip() or None,
        phone_keyword=q_phone.strip() or None,
        page=page,
        page_size=page_size,
    )
    return success_response(data={"items": items, "total": total})


# 说明：成员额度已改为「全平台统一」，不再支持按成员单独设置 / 批量设置 / 移除覆盖。
# 平台模型额度统一由 PUT /quotas/platform-setting 配置。
