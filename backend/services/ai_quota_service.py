"""AI quota service for per-user AI call limiting and usage tracking."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from core.timezone import beijing_now
from models.ai_models import AiPlatformQuotaSetting, AiModel, AiUsageLog, AiUserModelQuota

TZ = ZoneInfo("Asia/Shanghai")
SUCCEEDED_STATUSES = ("succeeded", "success", "completed")
FAILED_STATUSES = ("failed", "failure")


def _today_bounds() -> tuple[datetime, datetime]:
    """Return the current Beijing day as a half-open interval."""
    start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _platform_model_condition():
    """Match platform logs while keeping legacy records without model metadata."""
    return or_(
        AiModel.scope == "platform",
        and_(
            AiModel.scope.is_(None),
            or_(
                AiUsageLog.quota_scope.in_(("platform", "superuser")),
                AiUsageLog.quota_scope.is_(None),
            ),
        ),
    )


def get_valid_quota_limit(value: int | None) -> int | None:
    """将缺失或历史非法额度统一解释为未配置，不向业务层返回 0。"""
    try:
        limit = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return limit if limit and limit > 0 else None


def get_configured_quota_limit(value: int | None) -> int | None:
    """读取额度配置展示值；允许 0 表示已配置但暂停非超管使用。"""
    try:
        limit = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return limit if limit is not None and limit >= 0 else None


@dataclass(frozen=True)
class UsageFilters:
    user_name: str | None = None
    phone: str | None = None
    keyword: str | None = None
    model: str | None = None
    model_scope: str | None = None
    action: str | None = None
    result: str | None = None
    department: int | None = None
    caller_type: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    # 仅由服务端根据“我的模型”视图注入，不能由客户端直接指定任意用户。
    model_owner_id: int | None = None


def _clean_filter_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _parse_usage_time(value: str | None) -> datetime | None:
    text = _clean_filter_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if "T" in text else text, fmt)
        except ValueError:
            continue
    return None


DEPARTMENT_LABELS = {
    1: "测试部门",
    2: "开发部门",
    4: "产品部门",
    3: "运维部门",
    5: "其他部门",
}


def normalize_usage_status(status: str | None) -> str:
    """将历史调用状态归一为用户可见的成功、失败两态。"""
    value = str(status or "").strip().lower()
    if value in {"succeeded", "success", "completed"}:
        return "succeeded"
    return "failed"


def normalize_usage_result_filter(value: str | None) -> str | None:
    """只接受调用记录页面的成功、失败筛选，非法值按未筛选处理。"""
    text = str(value or "").strip().lower()
    if text in SUCCEEDED_STATUSES:
        return "succeeded"
    if text in FAILED_STATUSES:
        return "failed"
    return None


def usage_result_filter_condition(value: str | None):
    """将成功、失败筛选映射为数据库条件，历史空结果归入失败。"""
    if value == "succeeded":
        return AiUsageLog.status.in_(SUCCEEDED_STATUSES)
    if value == "failed":
        return or_(
            AiUsageLog.status.is_(None),
            ~AiUsageLog.status.in_(SUCCEEDED_STATUSES),
        )
    return None


def resolve_current_quota_limit(
    quota_scope: str | None,
    is_superuser: bool,
    platform_limit: int | None,
    personal_limit: int | None = None,
    model_scope: str | None = None,
) -> int | None:
    """Resolve the latest applicable daily limit for a usage record."""
    effective_scope = model_scope or quota_scope
    if effective_scope == "personal":
        return personal_limit
    if is_superuser or quota_scope == "superuser":
        return -1
    if quota_scope == "platform":
        return platform_limit
    return None


def _department_label(code: int | None) -> str:
    if code is None:
        return ""
    return DEPARTMENT_LABELS.get(code, str(code))


def normalize_usage_filters(
    user_name: str | None = None,
    phone: str | None = None,
    keyword: str | None = None,
    model: str | None = None,
    model_scope: str | None = None,
    action: str | None = None,
    result: str | None = None,
    department: int | None = None,
    caller_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    model_owner_id: int | None = None,
) -> UsageFilters:
    normalized_owner_id = None
    try:
        if model_owner_id is not None and int(model_owner_id) > 0:
            normalized_owner_id = int(model_owner_id)
    except (TypeError, ValueError):
        normalized_owner_id = None
    return UsageFilters(
        user_name=_clean_filter_text(user_name),
        phone=_clean_filter_text(phone),
        keyword=_clean_filter_text(keyword),
        model=_clean_filter_text(model),
        model_scope=model_scope if model_scope in {"platform", "personal"} else None,
        action=_clean_filter_text(action),
        result=normalize_usage_result_filter(result),
        department=department,
        caller_type=caller_type if caller_type in {"user", "system"} else None,
        start_time=_parse_usage_time(start_time),
        end_time=_parse_usage_time(end_time),
        model_owner_id=normalized_owner_id,
    )


def _personal_model_owner_condition(owner_id: int):
    """匹配模型所有人，兼容早期仅保存创建人的个人模型记录。"""
    return or_(
        AiModel.owner_user_id == owner_id,
        and_(AiModel.owner_user_id.is_(None), AiModel.created_by == owner_id),
    )


def _model_scope_filter_condition(model_scope: str, model_owner_id: int | None = None):
    """构造平台/个人模型统计条件，所有查询入口共用。"""
    if model_scope == "platform":
        platform_model_ids = select(AiModel.id).where(
            AiModel.scope == "platform",
        )
        legacy_model_ids = select(AiModel.id).where(AiModel.scope.is_(None))
        # 旧记录没有可用的模型范围时，按当时保存的额度范围保留平台调用。
        legacy_platform = and_(
            or_(
                AiUsageLog.model_id.is_(None),
                AiUsageLog.model_id.in_(legacy_model_ids),
            ),
            or_(
                AiUsageLog.quota_scope.in_(('platform', 'superuser')),
                AiUsageLog.quota_scope.is_(None),
            ),
        )
        return or_(AiUsageLog.model_id.in_(platform_model_ids), legacy_platform)

    personal_model_ids = select(AiModel.id).where(AiModel.scope == "personal")
    if model_owner_id is not None:
        personal_model_ids = personal_model_ids.where(_personal_model_owner_condition(model_owner_id))
    personal_condition = AiUsageLog.model_id.in_(personal_model_ids)

    legacy_personal_model_ids = select(AiModel.id).where(AiModel.scope.is_(None))
    if model_owner_id is not None:
        legacy_personal_model_ids = legacy_personal_model_ids.where(_personal_model_owner_condition(model_owner_id))
        legacy_personal_condition = and_(
            AiUsageLog.model_id.in_(legacy_personal_model_ids),
            AiUsageLog.quota_scope == "personal",
        )
    else:
        legacy_personal_condition = and_(
            or_(
                AiUsageLog.model_id.is_(None),
                AiUsageLog.model_id.in_(legacy_personal_model_ids),
            ),
            AiUsageLog.quota_scope == "personal",
        )
    return or_(personal_condition, legacy_personal_condition)


def build_usage_log_filter_conditions(
    filters: UsageFilters | None = None,
    user_id: int | None = None,
) -> list:
    """构造调用记录的统一筛选条件，查询和软删除共用。"""
    conditions = [AiUsageLog.is_deleted.is_(False)]
    if user_id is not None:
        conditions.append(AiUsageLog.user_id == user_id)
    if not filters:
        return conditions
    from models.models import User

    if filters.user_name:
        conditions.append(User.real_name.like(f"%{filters.user_name}%"))
    if filters.phone:
        conditions.append(User.phone.like(f"%{filters.phone}%"))
    if filters.keyword:
        conditions.append(or_(
            User.real_name.like(f"%{filters.keyword}%"),
            User.phone.like(f"%{filters.keyword}%"),
        ))
    if filters.model:
        conditions.append(AiUsageLog.model.like(f"%{filters.model}%"))
    if filters.model_scope:
        conditions.append(_model_scope_filter_condition(filters.model_scope, filters.model_owner_id))
    elif filters.model_owner_id is not None:
        # 所有人范围只有“我的模型”语义，缺少模型范围时也必须保持安全收敛。
        conditions.append(_model_scope_filter_condition("personal", filters.model_owner_id))
    if filters.action:
        conditions.append(or_(
            AiUsageLog.action.like(f"%{filters.action}%"),
            AiUsageLog.feature.like(f"%{filters.action}%"),
        ))
    if filters.result:
        conditions.append(usage_result_filter_condition(filters.result))
    if filters.department is not None:
        conditions.append(User.department == filters.department)
    if filters.caller_type == "user":
        conditions.append(AiUsageLog.user_id.isnot(None))
    elif filters.caller_type == "system":
        conditions.append(AiUsageLog.user_id.is_(None))
    if filters.start_time:
        conditions.append(AiUsageLog.created_at >= filters.start_time)
    if filters.end_time:
        conditions.append(AiUsageLog.created_at <= filters.end_time)
    return conditions


async def soft_delete_usage_logs(
    db: AsyncSession,
    filters: UsageFilters | None = None,
    ids: list[int] | None = None,
) -> int:
    """软删除符合筛选条件或指定 ID 的调用记录。"""
    from models.models import User

    conditions = build_usage_log_filter_conditions(filters)
    if ids:
        conditions.append(AiUsageLog.id.in_(ids))
    matching_ids = (
        select(AiUsageLog.id)
        .outerjoin(User, User.id == AiUsageLog.user_id)
        .where(*conditions)
    )
    result = await db.execute(
        update(AiUsageLog)
        .where(AiUsageLog.id.in_(matching_ids))
        .values(is_deleted=True, deleted_at=beijing_now())
    )
    await db.commit()
    return result.rowcount or 0


# ==================== Per-User Quota ====================


async def get_user_quota(db: AsyncSession, user_id: int) -> int | None:
    """获取用户平台模型日额度；全平台统一，由平台模型额度配置决定。

    额度不再按成员单独覆盖：超管设多少，所有非超管成员每人每天就是多少。
    """
    setting = await get_platform_quota_setting(db)
    limit = getattr(setting, "daily_limit", None) if setting else None
    return int(limit) if limit and int(limit) > 0 else None


async def get_platform_quota_setting(db: AsyncSession) -> AiPlatformQuotaSetting | None:
    """读取平台模型额度配置；未配置代表普通用户尚未开通平台模型额度。"""
    result = await db.execute(select(AiPlatformQuotaSetting).where(
        AiPlatformQuotaSetting.is_deleted.is_(False),
    ).order_by(AiPlatformQuotaSetting.id.asc()).limit(1))
    return result.scalar_one_or_none()


async def set_platform_quota_setting(
    db: AsyncSession, daily_limit: int, updated_by: int,
) -> AiPlatformQuotaSetting:
    if int(daily_limit) < 0:
        raise UnifiedException(code=400, message="平台模型日额度不能小于 0")
    setting = await get_platform_quota_setting(db)
    if setting is None:
        setting = AiPlatformQuotaSetting(daily_limit=daily_limit, updated_by=updated_by)
        db.add(setting)
    else:
        setting.daily_limit = daily_limit
        setting.updated_by = updated_by
    await db.flush()
    return setting


async def get_platform_model_usage(db: AsyncSession, user_id: int) -> int:
    """统计用户当天实际消费的平台模型调用。"""
    today_start, today_end = _today_bounds()
    result = await db.execute(
        select(func.count(AiUsageLog.id))
        .outerjoin(AiModel, AiModel.id == AiUsageLog.model_id)
        .where(
            AiUsageLog.user_id == user_id,
            AiUsageLog.quota_consumed.is_(True),
            AiUsageLog.is_deleted.is_(False),
            _platform_model_condition(),
            AiUsageLog.created_at >= today_start,
            AiUsageLog.created_at < today_end,
        )
    )
    return result.scalar_one() or 0


async def get_user_platform_quota_info(db: AsyncSession, user_id: int) -> dict[str, int | None]:
    """返回指定用户的平台模型额度快照，供管理端查看用户模型时使用。"""
    setting = await get_platform_quota_setting(db)
    from models.models import User

    is_superuser = bool((await db.execute(
        select(User.is_superuser).where(User.id == user_id)
    )).scalar_one_or_none())
    daily_limit = -1 if is_superuser else get_configured_quota_limit(setting.daily_limit if setting else None)
    today_used = await get_platform_model_usage(db, user_id)
    return {
        "daily_limit": daily_limit,
        "today_used": today_used,
        "remaining": -1 if is_superuser else (
            max(0, daily_limit - today_used) if daily_limit is not None else None
        ),
    }


async def get_users_platform_quota_info(db: AsyncSession, user_ids: set[int]) -> dict[int, dict[str, int | None]]:
    """批量返回用户的平台模型额度快照，避免管理列表逐行查询数据库。"""
    normalized_ids = {int(user_id) for user_id in user_ids if user_id}
    if not normalized_ids:
        return {}
    setting = await get_platform_quota_setting(db)
    daily_limit = get_configured_quota_limit(setting.daily_limit if setting else None)
    today_start, today_end = _today_bounds()
    usage_rows = await db.execute(
        select(AiUsageLog.user_id, func.count(AiUsageLog.id))
        .outerjoin(AiModel, AiModel.id == AiUsageLog.model_id)
        .where(
            AiUsageLog.user_id.in_(normalized_ids),
            AiUsageLog.quota_consumed.is_(True),
            AiUsageLog.is_deleted.is_(False),
            _platform_model_condition(),
            AiUsageLog.created_at >= today_start,
            AiUsageLog.created_at < today_end,
        )
        .group_by(AiUsageLog.user_id)
    )
    usage_map = dict(usage_rows.all())
    return {
        user_id: {
            "daily_limit": daily_limit,
            "today_used": usage_map.get(user_id, 0),
            "remaining": max(0, daily_limit - usage_map.get(user_id, 0)) if daily_limit is not None else None,
        }
        for user_id in normalized_ids
    }


async def check_user_ai_quota(db: AsyncSession, user_id: int, is_superuser: bool = False) -> tuple[bool, int, int | None, str]:
    """Check if a user can make an AI call.
    Returns (allowed, today_used, daily_limit, message).
    Super admins always have unlimited quota.
    """
    if is_superuser:
        return True, 0, -1, ""  # -1 means unlimited
    daily_limit = await get_user_quota(db, user_id)
    if daily_limit is None:
        return False, 0, None, "你当前没有可用的 AI 额度。请前往「AI模型配置」配置可用的平台模型或我的模型并设置日额度后再试。"

    used = await get_platform_model_usage(db, user_id)
    if used >= daily_limit:
        return False, used, daily_limit, f"今日 AI 配额已用完（{used}/{daily_limit}）"

    return True, used, daily_limit, ""


async def get_user_model_quota(db: AsyncSession, user_id: int, model_id: int) -> int | None:
    row = (await db.execute(select(AiUserModelQuota).where(
        AiUserModelQuota.user_id == user_id,
        AiUserModelQuota.model_id == model_id,
        AiUserModelQuota.is_deleted.is_(False),
    ))).scalar_one_or_none()
    limit = getattr(row, "daily_limit", None) if row else None
    return int(limit) if limit and int(limit) > 0 else None


async def get_user_model_quota_info(db: AsyncSession, user_id: int, model_id: int) -> dict[str, int | None]:
    """返回指定用户模型的日额度快照。"""
    daily_limit = await get_user_model_quota(db, user_id, model_id)
    today_start, today_end = _today_bounds()
    today_used = (await db.execute(select(func.count(AiUsageLog.id)).where(
        AiUsageLog.user_id == user_id,
        AiUsageLog.model_id == model_id,
        AiUsageLog.quota_consumed.is_(True),
        AiUsageLog.is_deleted.is_(False),
        AiUsageLog.created_at >= today_start,
        AiUsageLog.created_at < today_end,
    ))).scalar_one() or 0
    return {
        "daily_limit": daily_limit,
        "today_used": today_used,
        "remaining": max(0, daily_limit - today_used) if daily_limit is not None else None,
    }


async def get_user_usage_quota_stats(
    db: AsyncSession,
    user_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    today_mode: bool = False,
) -> dict:
    """按用户 + 时间范围统计平台模型 / 我的模型用量。

    - today_mode=True：附带今日额度上限与剩余（额度视角）。
    - today_mode=False：仅返回该时段成功 / 失败 / 扣费次数，不含上限
      （历史上限未存储，跨天也没有单一日上限）。
    """
    succeeded_statuses = SUCCEEDED_STATUSES
    if today_mode:
        start_time, today_end = _today_bounds()
        # 今日和“按天选择今天”统一使用服务端北京时间当天，避免客户端日期或旧参数串入额度视角。
        end_time = today_end - timedelta(microseconds=1)

    conditions = [
        AiUsageLog.user_id == user_id,
        AiUsageLog.is_deleted.is_(False),
    ]
    if start_time is not None:
        conditions.append(AiUsageLog.created_at >= start_time)
    if end_time is not None:
        conditions.append(AiUsageLog.created_at <= end_time)

    succeeded_expr = func.coalesce(func.sum(case((AiUsageLog.status.in_(succeeded_statuses), 1), else_=0)), 0)
    failed_expr = func.coalesce(func.sum(case((or_(
        AiUsageLog.status.is_(None),
        ~AiUsageLog.status.in_(succeeded_statuses),
    ), 1), else_=0)), 0)
    consumed_expr = func.coalesce(
        func.sum(case((AiUsageLog.quota_consumed.is_(True), func.coalesce(AiUsageLog.quota_count, 1)), else_=0)),
        0,
    )

    rows = (await db.execute(
        select(
            AiModel.scope.label("model_scope"),
            AiUsageLog.quota_scope,
            AiUsageLog.model_id,
            AiUsageLog.model,
            func.count(AiUsageLog.id),
            succeeded_expr,
            failed_expr,
            consumed_expr,
        )
        .outerjoin(AiModel, AiModel.id == AiUsageLog.model_id)
        .where(*conditions)
        .group_by(AiModel.scope, AiUsageLog.quota_scope, AiUsageLog.model_id, AiUsageLog.model)
    )).all()

    def effective_scope(model_scope: str | None, quota_scope: str | None) -> str:
        # 归属优先看模型真实范围；缺失时回退调用记录的额度范围；
        # 历史 None / 超管调用统一归入平台，与列表口径保持一致。
        if model_scope in ("platform", "personal"):
            return model_scope
        if quota_scope in ("platform", "personal"):
            return quota_scope
        return "platform"

    platform = {"total": 0, "succeeded": 0, "failed": 0, "consumed": 0}
    personal_map: dict[int | None, dict] = {}
    for model_scope, quota_scope, model_id, model_name, total, succeeded, failed, consumed in rows:
        bucket = platform if effective_scope(model_scope, quota_scope) == "platform" else personal_map.setdefault(
            model_id,
            {"model_id": model_id, "model_name": model_name or "", "total": 0, "succeeded": 0, "failed": 0, "consumed": 0},
        )
        bucket["total"] += int(total or 0)
        bucket["succeeded"] += int(succeeded or 0)
        bucket["failed"] += int(failed or 0)
        bucket["consumed"] += int(consumed or 0)
        if bucket is not platform and model_name and not bucket["model_name"]:
            bucket["model_name"] = model_name

    platform_block = {**platform, "limit": None, "used": None, "remaining": None}
    if today_mode:
        info = await get_user_platform_quota_info(db, user_id)
        platform_block["limit"] = info["daily_limit"]
        platform_block["used"] = info["today_used"]
        platform_block["remaining"] = info["remaining"]

        # 今日视角补齐已配置额度但今日暂无用量的我的模型，避免看不到额度上限。
        quota_rows = (await db.execute(
            select(AiUserModelQuota.model_id, AiModel.name)
            .outerjoin(AiModel, AiModel.id == AiUserModelQuota.model_id)
            .where(
                AiUserModelQuota.user_id == user_id,
                AiUserModelQuota.is_deleted.is_(False),
                AiUserModelQuota.daily_limit > 0,
            )
        )).all()
        for model_id, model_name in quota_rows:
            bucket = personal_map.setdefault(
                model_id,
                {"model_id": model_id, "model_name": model_name or "", "total": 0, "succeeded": 0, "failed": 0, "consumed": 0},
            )
            if model_name and not bucket["model_name"]:
                bucket["model_name"] = model_name
        for model_id, bucket in personal_map.items():
            if model_id is None:
                bucket.update({"limit": None, "used": bucket["consumed"], "remaining": None})
                continue
            model_info = await get_user_model_quota_info(db, user_id, model_id)
            bucket["limit"] = model_info["daily_limit"]
            bucket["used"] = model_info["today_used"]
            bucket["remaining"] = model_info["remaining"]
    else:
        for bucket in personal_map.values():
            bucket.update({"limit": None, "used": None, "remaining": None})

    personal_list = sorted(personal_map.values(), key=lambda item: item.get("model_name") or "")
    return {
        "today_mode": today_mode,
        "platform": platform_block,
        "personal": personal_list,
    }


async def check_model_ai_quota(db: AsyncSession, user, model: AiModel) -> tuple[bool, int, int | None, str, str]:
    """按实际模型检查平台或个人次数额度，返回最后一项额度范围。"""
    scope = getattr(model, "scope", "platform") or "platform"
    if scope == "platform" and bool(getattr(user, "is_superuser", False)):
        return True, 0, -1, "", "superuser"
    if scope == "platform":
        allowed, used, limit, message = await check_user_ai_quota(db, user.id)
        return allowed, used, limit, message, "platform"
    daily_limit = await get_user_model_quota(db, user.id, model.id)
    if daily_limit is None:
        return False, 0, None, "该我的模型未设置可用日额度", "personal"
    today_start, today_end = _today_bounds()
    used = (await db.execute(select(func.count(AiUsageLog.id)).where(
        AiUsageLog.user_id == user.id,
        AiUsageLog.model_id == model.id,
        AiUsageLog.quota_consumed.is_(True),
        AiUsageLog.is_deleted.is_(False),
        AiUsageLog.created_at >= today_start,
        AiUsageLog.created_at < today_end,
    ))).scalar_one() or 0
    if used >= daily_limit:
        return False, used, daily_limit, f"我的模型今日额度已用完（{used}/{daily_limit}）", "personal"
    return True, used, daily_limit, "", "personal"


async def set_user_model_quota(db: AsyncSession, user_id: int, model_id: int, daily_limit: int) -> AiUserModelQuota:
    if int(daily_limit) <= 0:
        raise UnifiedException(code=400, message="模型日额度必须大于 0")
    row = (await db.execute(select(AiUserModelQuota).where(
        AiUserModelQuota.user_id == user_id,
        AiUserModelQuota.model_id == model_id,
    ))).scalar_one_or_none()
    if row is None:
        row = AiUserModelQuota(user_id=user_id, model_id=model_id, daily_limit=daily_limit)
        db.add(row)
    else:
        row.daily_limit = daily_limit
        row.is_deleted = False
        row.deleted_at = None
    await db.flush()
    return row


async def list_users_with_quota_info(
    db: AsyncSession, keyword: str | None = None,
    name_keyword: str | None = None, phone_keyword: str | None = None,
    page: int = 1, page_size: int = 10
) -> tuple[list[dict], int]:
    """List all registered + enabled users with their quota info. For superadmin management.
    Returns (items, total_count)."""
    from models.models import User
    from sqlalchemy import or_, func

    base = select(User.id, User.real_name, User.phone, User.is_active,
                  User.is_superuser, User.is_manager, User.department, User.nick_name).where(User.is_superuser == False)
    count_base = select(func.count(User.id)).where(User.is_active == True, User.is_superuser == False)
    if keyword:
        kw = f"%{keyword}%"
        cond = or_(User.real_name.like(kw), User.phone.like(kw))
        base = base.where(cond)
        count_base = count_base.where(cond)
    if name_keyword:
        name_cond = User.real_name.like(f"%{name_keyword}%")
        base = base.where(name_cond)
        count_base = count_base.where(name_cond)
    if phone_keyword:
        phone_cond = User.phone.like(f"%{phone_keyword}%")
        base = base.where(phone_cond)
        count_base = count_base.where(phone_cond)

    # Total count
    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    # Paginated users
    result = await db.execute(
        base.where(User.is_active == True, User.is_superuser == False).order_by(User.id.asc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    users = result.all()

    # 全平台统一额度：每个非超管成员每日额度都等于平台模型额度配置。
    platform_setting = await get_platform_quota_setting(db)
    default_limit = get_configured_quota_limit(platform_setting.daily_limit if platform_setting else None)

    # 平台模型“已用”只统计实际消费调用，避免我的模型和未消费拒绝混入。
    today_start, today_end = _today_bounds()
    usage_rows = await db.execute(
        select(AiUsageLog.user_id, func.count(AiUsageLog.id))
        .outerjoin(AiModel, AiModel.id == AiUsageLog.model_id)
        .where(
            AiUsageLog.created_at >= today_start,
            AiUsageLog.created_at < today_end,
            AiUsageLog.quota_consumed.is_(True),
            AiUsageLog.is_deleted.is_(False),
            _platform_model_condition(),
        )
        .group_by(AiUsageLog.user_id)
    )
    usage_map = dict(usage_rows.all())

    total_usage_rows = await db.execute(
        select(AiUsageLog.user_id, func.count(AiUsageLog.id))
        .outerjoin(AiModel, AiModel.id == AiUsageLog.model_id)
        .where(
            AiUsageLog.quota_consumed.is_(True),
            AiUsageLog.is_deleted.is_(False),
            _platform_model_condition(),
        )
        .group_by(AiUsageLog.user_id)
    )
    total_usage_map = dict(total_usage_rows.all())

    items = []
    for uid, name, phone, active, superuser, manager, dept, nick in users:
        items.append({
            "user_id": uid,
            "real_name": name or "",
            "phone": phone or "",
            "is_active": active,
            "is_superuser": superuser,
            "is_manager": manager,
            "department": dept,
            "nick_name": nick or "",
            "daily_limit": default_limit,
            "today_used": usage_map.get(uid, 0),
            "total_used": total_usage_map.get(uid, 0),
        })
    return items, total


# ==================== Usage Logging ====================


async def log_ai_usage(
    db: AsyncSession,
    user_id: int | None,
    action: str,
    model: str | None = None,
    model_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    tokens_estimated: int | None = None,
    feature: str | None = None,
    status: str = "succeeded",
    failure_reason: str | None = None,
    quota_consumed: bool = True,
    quota_scope: str | None = None,
    call_group_id: str | None = None,
) -> AiUsageLog:
    """Record an AI call for quota tracking."""
    log = AiUsageLog(
        user_id=user_id,
        action=action,
        model=model,
        model_id=model_id,
        target_type=target_type,
        target_id=target_id,
        tokens_estimated=tokens_estimated,
        feature=feature,
        status=status,
        failure_reason=failure_reason,
        quota_consumed=quota_consumed,
        quota_count=1 if quota_consumed else 0,
        quota_scope=quota_scope,
        call_group_id=call_group_id,
    )
    db.add(log)
    await db.flush()
    return log


# ==================== Usage Summary ====================


async def get_usage_summary(
    db: AsyncSession,
    user_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    include_stats: bool = False,
    filters: UsageFilters | None = None,
) -> dict:
    """Get paginated AI usage logs. If user_id is None, return all (superadmin view)."""
    from models.models import User
    today_start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    base = (
        select(
            AiUsageLog,
            User.real_name.label("real_name"),
            User.phone.label("phone"),
            User.is_superuser.label("is_superuser"),
            AiModel.scope.label("model_scope"),
        )
        .outerjoin(User, User.id == AiUsageLog.user_id)
        .outerjoin(AiModel, AiModel.id == AiUsageLog.model_id)
    )
    # 明细与概览共用同一套筛选条件，保证数字可以回溯到明细。
    base = base.where(*build_usage_log_filter_conditions(filters, user_id=user_id))

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(AiUsageLog.created_at.desc()).offset(offset).limit(page_size)
    )
    logs = result.all()

    platform_setting = await get_platform_quota_setting(db)
    platform_daily_limit = get_configured_quota_limit(platform_setting.daily_limit if platform_setting else None)
    personal_quota_map = {}
    user_ids = {log.user_id for log, *_ in logs if log.user_id is not None}
    model_ids = {log.model_id for log, *_ in logs if log.model_id is not None}
    if user_ids and model_ids:
        quota_rows = await db.execute(
            select(
                AiUserModelQuota.user_id,
                AiUserModelQuota.model_id,
                AiUserModelQuota.daily_limit,
            ).where(
                AiUserModelQuota.user_id.in_(user_ids),
                AiUserModelQuota.model_id.in_(model_ids),
                AiUserModelQuota.is_deleted.is_(False),
            )
        )
        personal_quota_map = {
            (user_id, model_id): get_valid_quota_limit(daily_limit)
            for user_id, model_id, daily_limit in quota_rows.all()
        }

    def current_quota_limit(log, is_superuser: bool, model_scope: str | None) -> int | None:
        return resolve_current_quota_limit(
            log.quota_scope,
            is_superuser,
            platform_daily_limit,
            personal_quota_map.get((log.user_id, log.model_id)),
            model_scope,
        )

    today_base = base.where(AiUsageLog.created_at >= today_start)
    today_result = await db.execute(select(func.count()).select_from(today_base.subquery()))
    today_used = today_result.scalar_one()

    data = {
        "items": [{
            "id": log.id,
            "user_id": log.user_id,
            "user_name": real_name or "",
            "phone": phone or "",
            "action": log.action,
            "model": log.model,
            "call_count": 1,
            "model_id": log.model_id,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "tokens_estimated": log.tokens_estimated,
            "input_tokens": log.input_tokens,
            "output_tokens": log.output_tokens,
            "cache_tokens": log.cache_tokens,
            "total_tokens": log.total_tokens,
            "provider_request_id": log.provider_request_id,
            "feature": log.feature,
            "status": normalize_usage_status(log.status),
            "failure_reason": log.failure_reason or (
                "历史调用未保留失败原因" if normalize_usage_status(log.status) == "failed" else None
            ),
            "quota_consumed": bool(log.quota_consumed),
            "quota_count": log.quota_count,
            "quota_scope": log.quota_scope,
            "model_scope": model_scope,
            "quota_limit": current_quota_limit(log, bool(is_superuser), model_scope),
            "call_group_id": log.call_group_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        } for log, real_name, phone, is_superuser, model_scope in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "today_used": today_used,
    }

    if include_stats:
        data["stats"] = await get_usage_stats(db, user_id=user_id, filters=filters)

    return data


async def get_usage_stats(
    db: AsyncSession,
    user_id: int | None = None,
    filters: UsageFilters | None = None,
) -> dict:
    """Aggregate AI usage statistics. If user_id is set, only count that user."""
    from datetime import timedelta
    from models.models import User

    now = datetime.now(TZ)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    def apply_filters(stmt, *, user_joined: bool = False, active_filters: UsageFilters | None = filters):
        if active_filters and (active_filters.user_name or active_filters.phone or active_filters.keyword or active_filters.department is not None) and not user_joined:
            stmt = stmt.outerjoin(User, User.id == AiUsageLog.user_id)
        return stmt.where(*build_usage_log_filter_conditions(active_filters, user_id=user_id))

    period_filters = replace(filters, start_time=None, end_time=None) if filters else None

    async def count_since(start_at: datetime | None = None, active_filters: UsageFilters | None = filters) -> int:
        stmt = select(func.count(AiUsageLog.id))
        if start_at is not None:
            stmt = stmt.where(AiUsageLog.created_at >= start_at)
        stmt = apply_filters(stmt, active_filters=active_filters)
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def count_matching(*conditions) -> int:
        stmt = select(func.count(AiUsageLog.id))
        if conditions:
            stmt = stmt.where(*conditions)
        result = await db.execute(apply_filters(stmt))
        return result.scalar_one() or 0

    async def sum_matching(value, *conditions) -> int:
        stmt = select(func.coalesce(func.sum(value), 0))
        if conditions:
            stmt = stmt.where(*conditions)
        result = await db.execute(apply_filters(stmt))
        return int(result.scalar_one() or 0)

    scope_total_stmt = apply_filters(select(func.count(AiUsageLog.id)))
    scope_total_result = await db.execute(scope_total_stmt)
    scope_total_calls = scope_total_result.scalar_one() or 0

    def percentage(count: int) -> float:
        if scope_total_calls <= 0:
            return 0.0
        return round((count or 0) * 100 / scope_total_calls, 1)

    total_calls = await count_since()
    succeeded_statuses = ("succeeded", "success", "completed")
    quota_consumed_calls = await sum_matching(
        func.coalesce(AiUsageLog.quota_count, 1),
        AiUsageLog.quota_consumed.is_(True),
    )
    succeeded_calls = await count_matching(AiUsageLog.status.in_(succeeded_statuses))
    failed_calls = await count_matching(usage_result_filter_condition("failed"))
    today_calls = await count_since(today_start, period_filters)
    week_calls = await count_since(week_start, period_filters)
    month_calls = await count_since(month_start, period_filters)
    year_calls = await count_since(year_start, period_filters)

    active_users_stmt = select(func.count(func.distinct(AiUsageLog.user_id))).where(AiUsageLog.user_id.isnot(None))
    active_users_result = await db.execute(apply_filters(active_users_stmt))
    active_users = active_users_result.scalar_one() or 0

    today_active_stmt = select(func.count(func.distinct(AiUsageLog.user_id))).where(
        AiUsageLog.created_at >= today_start,
        AiUsageLog.user_id.isnot(None),
    )
    today_active_result = await db.execute(apply_filters(today_active_stmt))
    today_active_users = today_active_result.scalar_one() or 0

    action_stmt = (
        select(AiUsageLog.action, AiUsageLog.feature, func.count(AiUsageLog.id).label("count"))
        .group_by(AiUsageLog.action, AiUsageLog.feature)
        .order_by(func.count(AiUsageLog.id).desc())
    )
    action_rows = await db.execute(apply_filters(action_stmt))

    model_stmt = (
        select(AiUsageLog.model, func.count(AiUsageLog.id).label("count"))
        .where(AiUsageLog.model.isnot(None), AiUsageLog.model != "")
        .group_by(AiUsageLog.model)
        .order_by(func.count(AiUsageLog.id).desc())
        .limit(6)
    )
    model_rows = await db.execute(apply_filters(model_stmt))

    user_stmt = (
        select(
            AiUsageLog.user_id,
            User.real_name,
            User.phone,
            User.department,
            User.is_active,
            User.is_superuser,
            func.count(AiUsageLog.id).label("count"),
        )
        .outerjoin(User, User.id == AiUsageLog.user_id)
        .where(AiUsageLog.user_id.isnot(None))
        .group_by(
            AiUsageLog.user_id,
            User.real_name,
            User.phone,
            User.department,
            User.is_active,
            User.is_superuser,
        )
        .order_by(func.count(AiUsageLog.id).desc())
        .limit(5)
    )
    user_rows = await db.execute(apply_filters(user_stmt, user_joined=True))
    user_items = user_rows.all()
    platform_quota_map = await get_users_platform_quota_info(
        db,
        {user_id for user_id, *_ in user_items if user_id is not None},
    )

    unattributed_stmt = select(func.count(AiUsageLog.id)).where(AiUsageLog.user_id.is_(None))
    unattributed_result = await db.execute(apply_filters(unattributed_stmt))
    unattributed_calls = unattributed_result.scalar_one() or 0

    action_items = [{
        "action": action or "",
        "feature": feature or "",
        "count": count or 0,
        "percentage": percentage(count),
    } for action, feature, count in action_rows.all()]
    model_items = [{"model": model or "", "count": count or 0, "percentage": percentage(count)} for model, count in model_rows.all()]

    return {
        # total_calls 保留给既有页面，actual_calls 明确表示已记录的一次真实模型请求。
        "actual_calls": total_calls,
        "total_calls": total_calls,
        "quota_consumed_calls": quota_consumed_calls,
        "succeeded_calls": succeeded_calls,
        "failed_calls": failed_calls,
        "today_calls": today_calls,
        "week_calls": week_calls,
        "month_calls": month_calls,
        "year_calls": year_calls,
        "active_users": active_users,
        "today_active_users": today_active_users,
        "actions": action_items,
        "models": model_items,
        "top_users": [{
            "user_id": user_id,
            "user_name": real_name or "",
            "phone": phone or "",
            "department": _department_label(department) if department else "",
            "status_label": "激活" if is_active else "禁用",
            "count": count or 0,
            "percentage": percentage(count),
            "platform_quota": (
                {"daily_limit": -1, "today_used": 0, "remaining": -1}
                if is_superuser
                else platform_quota_map.get(
                    user_id,
                    {"daily_limit": None, "today_used": 0, "remaining": None},
                )
            ),
        } for user_id, real_name, phone, department, is_active, is_superuser, count in user_items],
        "unattributed_calls": unattributed_calls,
        "unattributed_percentage": percentage(unattributed_calls),
    }
