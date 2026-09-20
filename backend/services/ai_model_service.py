"""AI model management service."""
import logging
from datetime import datetime
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.timezone import beijing_now
from models.ai_models import AiModel, AiUserModelQuota
from models.models import User
from llm.providers import OpenAICompatProvider, BaseLLMProvider
from utils.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)

REASONING_FEATURE_FLAGS = {"reasoning", "supports_reasoning", "thinking"}
REASONING_MODEL_HINTS = (
    "reasoner", "reasoning", "thinking", "deepseek-r1", "qwq",
    "o1", "o3", "o4", "grok-3-mini", "claude-3.7-sonnet-thinking",
)


def model_required_message(feature: str) -> str:
    return "当前没有可用的 AI 模型，请在 AI 模型配置中启用模型并配置可用日额度后再试"


def model_supports_reasoning(model: AiModel | None) -> bool:
    """只根据已测试结果判断是否可向用户展示思考过程，避免名称猜测造成误导。"""
    return bool(model and getattr(model, "reasoning_status", "unknown") == "supported")


def build_ai_model_preview(model, prompt_previews: dict[str, str] | None = None) -> dict:
    """组装工作台 AI 预检的通用模型状态，提示词由具体入口补充。"""
    result = {
        "id": model.id,
        "name": model.name,
        "model": model.model,
        "connectivity_status": getattr(model, "connectivity_status", "unknown"),
        "reasoning_status": getattr(model, "reasoning_status", "unknown"),
        "supports_reasoning": model_supports_reasoning(model),
    }
    result.update(prompt_previews or {})
    return result


def _looks_like_api_key(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    return text.startswith(("sk-", "sk_")) or len(text) >= 20


def resolve_model_api_key(model: AiModel) -> str | None:
    """Return a usable API key from saved model data."""
    saved = (model.api_key_encrypted or "").strip()
    if not saved:
        return None
    try:
        api_key = decrypt(saved, settings.SECRET_KEY)
        return api_key.strip() or None
    except Exception:
        if _looks_like_api_key(saved):
            logger.warning("Using plaintext API key fallback for model %s", model.id)
            return saved
        logger.exception("Failed to decrypt API key for model %s", model.id)
        return None


def mask_model_api_key(model: AiModel) -> str | None:
    """Return first 5 chars plus asterisks without exposing the full key."""
    api_key = resolve_model_api_key(model)
    if not api_key or len(api_key) <= 5:
        return "已配置" if model.api_key_encrypted else None
    return f"{api_key[:5]}******"


# ==================== CRUD ====================


def _not_deleted_criterion():
    is_deleted = getattr(AiModel, "is_deleted", None)
    if is_deleted is None:
        return None
    return is_deleted == False


def _apply_not_deleted(stmt):
    criterion = _not_deleted_criterion()
    if criterion is None:
        return stmt
    return stmt.where(criterion)


def _is_model_deleted(model: AiModel | None) -> bool:
    return bool(getattr(model, "is_deleted", False))


async def list_models(db: AsyncSession) -> list[AiModel]:
    result = await db.execute(
        _apply_not_deleted(select(AiModel))
        .order_by(AiModel.id.asc())
    )
    return list(result.scalars().all())


def _tab_conditions(tab: str, current_user_id: int, is_superuser: bool):
    """按页签返回 scope + 归属可见性条件，语义与原前端过滤保持一致。

    mine：本人的“我的模型”（personal 且 owner 为本人）。
    platform：平台模型（启用 / 超管 / 本人所有 三者之一可见）。
    users：他人的“我的模型”（personal 且 owner 非本人，仅超管可见）。
    """
    conditions = []
    if tab == "platform":
        conditions.append(AiModel.scope == "platform")
        if not is_superuser:
            conditions.append(
                or_(AiModel.enabled.is_(True), AiModel.owner_user_id == current_user_id)
            )
    elif tab == "users":
        conditions.append(AiModel.scope == "personal")
        conditions.append(
            or_(AiModel.owner_user_id.is_(None), AiModel.owner_user_id != current_user_id)
        )
    else:  # mine
        conditions.append(AiModel.scope == "personal")
        conditions.append(AiModel.owner_user_id == current_user_id)
    return conditions


async def query_models_page(
    db: AsyncSession,
    *,
    tab: str,
    current_user_id: int,
    is_superuser: bool,
    model_name: str | None = None,
    model_identifier: str | None = None,
    enabled: str | None = None,
    connectivity_status: str | None = None,
    creator_name: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[AiModel], int]:
    """按页签 + 筛选 + 分页查询模型列表，返回 (当前页数据, 总数)。"""
    stmt = _apply_not_deleted(select(AiModel))
    for condition in _tab_conditions(tab, current_user_id, is_superuser):
        stmt = stmt.where(condition)

    if model_name and model_name.strip():
        stmt = stmt.where(AiModel.name.ilike(f"%{model_name.strip()}%"))
    if model_identifier and model_identifier.strip():
        stmt = stmt.where(AiModel.model.ilike(f"%{model_identifier.strip()}%"))
    if enabled == "enabled":
        stmt = stmt.where(AiModel.enabled.is_(True))
    elif enabled == "disabled":
        stmt = stmt.where(AiModel.enabled.is_(False))
    if connectivity_status:
        stmt = stmt.where(AiModel.connectivity_status == connectivity_status)
    if creator_name and creator_name.strip():
        owner_id_expr = func.coalesce(AiModel.owner_user_id, AiModel.created_by)
        owner_subquery = select(User.id).where(User.real_name.ilike(f"%{creator_name.strip()}%"))
        stmt = stmt.where(owner_id_expr.in_(owner_subquery))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    offset = max(0, (page - 1) * page_size)
    rows = await db.execute(
        stmt.order_by(AiModel.created_at.desc(), AiModel.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    return list(rows.scalars().all()), int(total)


async def has_enabled_platform_model(db: AsyncSession) -> bool:
    """是否存在启用中的平台模型（用于超管额度是否生效的提示，与分页无关）。"""
    stmt = (
        _apply_not_deleted(select(AiModel.id))
        .where(AiModel.scope == "platform", AiModel.enabled.is_(True))
        .limit(1)
    )
    return await db.scalar(stmt) is not None


async def get_model(db: AsyncSession, model_id: int) -> AiModel | None:
    model = await db.get(AiModel, model_id)
    if not model or _is_model_deleted(model):
        return None
    return model


async def create_model(db: AsyncSession, data: dict) -> AiModel:
    """Create a model. `api_key` in data will be encrypted."""
    raw_key = data.pop("api_key", None)
    connectivity_verified = bool(data.pop("connectivity_verified", False))
    reasoning_status_in = data.pop("reasoning_status", None)
    reasoning_profile_in = data.pop("reasoning_profile", None)
    usage_status_in = data.pop("usage_status", None)

    model = AiModel(**data)
    if connectivity_verified:
        model.connectivity_status = "passed"
        model.connectivity_checked_at = beijing_now()
    # 新建弹窗内已完成的思考模式检测结果一并落库（探测已通过连通性前置校验，reasoning_status 才会是三态之一）
    if reasoning_status_in in ("supported", "unsupported"):
        model.reasoning_status = reasoning_status_in
        model.reasoning_checked_at = beijing_now()
        if reasoning_profile_in:
            model.reasoning_profile = reasoning_profile_in
    # 新建弹窗内模型能力检测得到的用量统计结果一并落库（三合一探针一次返回，与思考模式同源）
    if usage_status_in in ("supported", "unsupported", "unknown"):
        model.usage_status = usage_status_in
        model.usage_checked_at = beijing_now() if usage_status_in == "supported" else None
    if raw_key and raw_key.strip():
        model.api_key_encrypted = encrypt(raw_key.strip(), settings.SECRET_KEY)
    db.add(model)
    await db.flush()
    return model


async def update_model(db: AsyncSession, model: AiModel, data: dict) -> AiModel:
    """Update a model. If `api_key` provided, re-encrypt."""
    raw_key = data.pop("api_key", None)
    connectivity_verified = data.pop("connectivity_verified", None)
    # 「模型能力检测」在弹窗内对改动后的配置重新探测得到的结果，随保存带上；
    # 先弹出，避免下面的通用赋值把它们当普通字段写入后又被 connection_changed 分支重置。
    reasoning_status_in = data.pop("reasoning_status", None)
    reasoning_profile_in = data.pop("reasoning_profile", None)
    usage_status_in = data.pop("usage_status", None)
    # 仅当接口地址 / 模型名 / API Key 实际发生变化时，才认为连接配置改变。
    # 编辑表单每次保存都会带上 base_url、model 字段（即便未修改），
    # 不能仅凭字段存在就判定为“已变更”，否则会把已检测的连通性 / 思考模式状态误重置为未检测。
    new_base_url = data.get("base_url")
    new_model = data.get("model")
    new_provider = data.get("provider")
    base_url_changed = new_base_url is not None and new_base_url != model.base_url
    model_changed = new_model is not None and new_model != model.model
    provider_changed = new_provider is not None and new_provider != model.provider
    key_changed = bool(raw_key and raw_key.strip())
    connection_changed = base_url_changed or model_changed or provider_changed or key_changed

    for key, value in data.items():
        # max_output_tokens 是可选配置；显式传 null 代表清空，恢复使用模型默认上限。
        # 其他字段继续保持原有的 None 忽略语义，避免改变未提交字段的更新行为。
        if value is not None or key == "max_output_tokens":
            setattr(model, key, value)
    if raw_key and raw_key.strip():
        model.api_key_encrypted = encrypt(raw_key.strip(), settings.SECRET_KEY)
    if connection_changed:
        model.connectivity_status = "passed" if connectivity_verified else "unknown"
        model.connectivity_checked_at = beijing_now() if connectivity_verified else None
        # 配置变了：若本次同时带回了新配置的能力检测结果就落库，否则回到未检测。
        if reasoning_status_in in ("supported", "unsupported"):
            model.reasoning_status = reasoning_status_in
            model.reasoning_checked_at = beijing_now()
            model.reasoning_profile = reasoning_profile_in or "chat_template"
        else:
            model.reasoning_status = "unknown"
            model.reasoning_checked_at = None
            model.reasoning_profile = "chat_template"
        if usage_status_in in ("supported", "unsupported", "unknown"):
            model.usage_status = usage_status_in
            model.usage_checked_at = beijing_now() if usage_status_in == "supported" else None
        else:
            model.usage_status = "unknown"
            model.usage_checked_at = None
    else:
        # 配置未变但在弹窗内重新检测过（同配置复测）：有结果就更新，无则保持原状。
        if reasoning_status_in in ("supported", "unsupported"):
            model.reasoning_status = reasoning_status_in
            model.reasoning_checked_at = beijing_now()
            if reasoning_profile_in:
                model.reasoning_profile = reasoning_profile_in
        if usage_status_in in ("supported", "unsupported", "unknown"):
            model.usage_status = usage_status_in
            model.usage_checked_at = beijing_now() if usage_status_in == "supported" else None
    await db.flush()
    return model


async def delete_model(db: AsyncSession, model: AiModel) -> None:
    if hasattr(model, "is_deleted"):
        model.is_deleted = True
    if hasattr(model, "deleted_at"):
        model.deleted_at = datetime.now()
    model.enabled = False
    quota_rows = (await db.execute(
        select(AiUserModelQuota).where(AiUserModelQuota.model_id == model.id)
    )).scalars().all()
    for row in quota_rows:
        row.is_deleted = True
        row.deleted_at = datetime.now()
    await db.flush()


def _reset_model_detection(model: AiModel) -> None:
    """把模型三项检测状态重置为未检测，供配置人员重新检查。"""
    model.connectivity_status = "unknown"
    model.connectivity_checked_at = None
    model.reasoning_status = "unknown"
    model.reasoning_checked_at = None
    model.usage_status = "unknown"
    model.usage_checked_at = None


async def invalidate_owner_platform_models(
    db: AsyncSession,
    owner_user_id: int,
    *,
    include_personal: bool = False,
    reason: str = "原超管权限已取消",
) -> int:
    """失效其名下模型（默认仅平台模型），停用/删除账号时连带“我的模型”。

    失效即：停用 + 记录原因 + 重置三项检测状态；保留历史配置与调用记录，
    恢复后需由具备权限的配置人员确认是否再次启用。
    """
    query = _apply_not_deleted(select(AiModel)).where(
        AiModel.owner_user_id == owner_user_id,
    )
    if not include_personal:
        query = query.where(AiModel.scope == "platform")
    models = (await db.execute(query)).scalars().all()
    for model in models:
        model.enabled = False
        model.invalidated_reason = reason
        _reset_model_detection(model)
    await db.flush()
    return len(models)


# ==================== Model Routing ====================


def _is_model_visible_to_user(user, model: AiModel) -> bool:
    scope = getattr(model, "scope", "platform") or "platform"
    if scope == "platform":
        return True
    owner_id = getattr(model, "owner_user_id", None) or getattr(model, "created_by", None)
    return owner_id == getattr(user, "id", None)


def sort_models_for_user_feature(user, models: list[AiModel], feature: str = "") -> list[AiModel]:
    """按平台模型优先、同范围模型 ID 升序返回当前用户可见模型。"""
    candidates = [
        model for model in models
        if _is_model_visible_to_user(user, model)
        and bool(getattr(model, "enabled", False))
        and not getattr(model, "invalidated_reason", None)
    ]
    return sorted(
        candidates,
        key=lambda model: (
            0 if (getattr(model, "scope", "platform") or "platform") == "platform" else 1,
            model.id,
        ),
    )


MAX_CANDIDATE_MODELS = 3


async def get_candidate_models_for_feature(
    db: AsyncSession, feature: str, limit: int = MAX_CANDIDATE_MODELS, current_user=None
) -> list[AiModel]:
    """返回可调用模型；保留动作参数以兼容现有调用链，但不参与模型筛选。"""
    stmt = _apply_not_deleted(
        select(AiModel).where(AiModel.enabled == True, AiModel.invalidated_reason.is_(None))
    ).order_by(AiModel.id.asc())
    result = await db.execute(stmt)
    models = list(result.scalars().all())

    if not models:
        return []

    if current_user is None:
        return models[:limit]

    ordered = sort_models_for_user_feature(current_user, models, feature)

    return ordered[:limit]


async def get_routable_models_for_feature(
    db: AsyncSession, feature: str, limit: int = MAX_CANDIDATE_MODELS, current_user=None,
) -> list[AiModel]:
    """Return candidates that can be routed now, including quota availability.

    This is a read-only preview. It checks the same quota rule used before a
    real call, but it does not reserve or consume any quota.
    """
    candidates = await get_candidate_models_for_feature(
        db, feature, limit=max(limit, 50), current_user=current_user,
    )
    if not current_user:
        return candidates[:limit]
    from services.ai_quota_service import check_model_ai_quota

    routable: list[AiModel] = []
    for candidate in candidates:
        allowed, _used, _daily_limit, _message, _scope = await check_model_ai_quota(
            db, current_user, candidate,
        )
        if allowed:
            routable.append(candidate)
        if len(routable) >= limit:
            break
    return routable


def is_retryable_llm_error(exc: Exception) -> bool:
    """Return True if this error is likely model-specific and worth retrying with another model."""
    msg = str(exc).lower()
    # Non-retryable: auth, model config, content issues
    if "401" in msg or "403" in msg or "unauthorized" in msg:
        return False
    if "404" in msg:
        return False
    if "context_length_exceeded" in msg or "content_filter" in msg:
        return False
    # Retryable: transient, quota, connectivity
    if "timeout" in msg or "长时间未返回新内容" in msg or "connect" in msg or "name or service not known" in msg:
        return True
    if "500" in msg or "503" in msg or "502" in msg:
        return True
    if "429" in msg or "rate limit" in msg or "quota" in msg or "insufficient" in msg:
        return True
    if "localprotocolerror" in msg or "remoteprotocolerror" in msg:
        return True
    # Default: retry unknown errors
    return True


async def get_provider_for_model(model: AiModel) -> BaseLLMProvider:
    """Create a provider instance for a specific model."""
    api_key = resolve_model_api_key(model) if model.api_key_encrypted else ""
    return OpenAICompatProvider(
        api_key=api_key or "",
        base_url=model.base_url,
        model=model.model,
        wire_api=getattr(model, "provider", "openai-compat"),
        # 已检测为具备思考模式的模型：调用时自动开启思考，让功能内展示思考过程。
        enable_thinking=model_supports_reasoning(model),
        thinking_profile=getattr(model, "reasoning_profile", "chat_template"),
    )


# ==================== Balance ====================


async def query_model_balance(model: AiModel) -> str | None:
    """Query DeepSeek balance. Returns formatted string or None."""
    if "deepseek.com" not in (model.base_url or "").lower():
        return None
    if not model.api_key_encrypted:
        return None
    api_key = resolve_model_api_key(model)
    if not api_key:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.deepseek.com/user/balance",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                logger.warning("DeepSeek balance check failed: %s", resp.status_code)
                return None
            data = resp.json()
            infos = data.get("balance_infos", [])
            if not infos:
                return None
            total = infos[0].get("total_balance", "?")
            currency = infos[0].get("currency", "¥")
            return f"{total} {currency}"
    except Exception:
        logger.exception("Failed to query model balance")
        return None
