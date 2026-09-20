from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.response import UnifiedException, success_response
from core.permissions import is_manager
from core.security import check_manager_permission, get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import ExecutionSet, Project, SchedulePolicy, ScheduleRunLog, User
from services.schedule_utils import upcoming_trigger_minutes, next_trigger_time, schedule_text
from utils.audit_logger import log_operation

router = APIRouter()


class SchedulePolicyIn(BaseModel):
    name: str
    description: str | None = None
    schedule_type: str = "daily_times"
    schedule_config: dict = Field(default_factory=dict)
    cron_expression: str | None = None
    max_references: int | None = None
    is_enabled: bool = True


def _validate_policy_data(data: SchedulePolicyIn):
    if data.schedule_type not in {"daily_times", "weekly_times", "interval", "cron"}:
        raise UnifiedException(code=400, message="不支持的执行策略类型")
    if data.max_references is not None and data.max_references < 1:
        raise UnifiedException(code=400, message="最大引用次数必须大于0")
    next_time = next_trigger_time(data.schedule_type, data.schedule_config, data.cron_expression, beijing_now())
    if data.is_enabled and not next_time:
        raise UnifiedException(code=400, message="执行策略时间配置无效")
    return next_time


async def _ensure_no_enabled_time_conflict(
    db: AsyncSession,
    data: SchedulePolicyIn,
    current_policy_id: int | None = None,
):
    if not data.is_enabled:
        return
    base = beijing_now()
    new_minutes = upcoming_trigger_minutes(
        data.schedule_type,
        data.schedule_config,
        data.cron_expression,
        base,
        limit=40,
        horizon_days=31,
    )
    if not new_minutes:
        return
    query = select(SchedulePolicy).where(
        SchedulePolicy.is_deleted == False,
        SchedulePolicy.is_enabled == True,
    )
    if current_policy_id:
        query = query.where(SchedulePolicy.id != current_policy_id)
    result = await db.execute(query)
    for policy in result.scalars().all():
        existing_minutes = upcoming_trigger_minutes(
            policy.schedule_type,
            policy.schedule_config,
            policy.cron_expression,
            base,
            limit=40,
            horizon_days=31,
        )
        conflict = sorted(new_minutes & existing_minutes)
        if conflict:
            conflict_text = conflict[0].strftime("%Y-%m-%d %H:%M")
            raise UnifiedException(
                code=400,
                message=f"执行时间与已启用策略「{policy.name}」冲突：{conflict_text}",
            )


async def _reference_count_map(db: AsyncSession, policy_ids: list[int]) -> dict[int, int]:
    if not policy_ids:
        return {}
    result = await db.execute(
        select(ExecutionSet.schedule_policy_id, func.count(ExecutionSet.id))
        .where(
            ExecutionSet.schedule_policy_id.in_(policy_ids),
            ExecutionSet.is_deleted == False,
        )
        .group_by(ExecutionSet.schedule_policy_id)
    )
    return {row[0]: row[1] for row in result.all()}


async def _audit_policy_operation(db: AsyncSession, user: User, operation: str, policy: SchedulePolicy, description: str):
    await log_operation(
        db=db,
        user_id=user.id,
        user_name=user.real_name or user.nick_name or "未知用户",
        module="schedule_policy",
        operation=operation,
        target_id=policy.id,
        target_name=policy.name,
        description=description,
    )


@router.get("/")
async def list_schedule_policies(
    name: str | None = None,
    creator: str | None = None,
    is_enabled: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(SchedulePolicy, User.real_name.label("creator_name"))
        .outerjoin(User, SchedulePolicy.created_by == User.id)
        .where(SchedulePolicy.is_deleted == False)
    )
    if name:
        query = query.where(SchedulePolicy.name.contains(name))
    if creator:
        query = query.where(User.real_name.contains(creator))
    if is_enabled is not None:
        query = query.where(SchedulePolicy.is_enabled == is_enabled)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    enabled_total = (await db.execute(
        select(func.count()).select_from(query.where(SchedulePolicy.is_enabled == True).subquery())
    )).scalar() or 0
    query = query.order_by(SchedulePolicy.id.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()
    policies = [policy for policy, _creator_name in rows]
    ref_counts = await _reference_count_map(db, [p.id for p in policies])
    data = []
    for policy, creator_name in rows:
        max_refs = policy.max_references or settings.SCHEDULE_POLICY_DEFAULT_MAX_REFERENCES
        if is_manager(current_user):
            item = {
                "id": policy.id,
                "name": policy.name,
                "description": policy.description,
                "schedule_type": policy.schedule_type,
                "cron_expression": policy.cron_expression,
                "schedule_text": schedule_text(policy.schedule_type, policy.schedule_config, policy.cron_expression),
                "reference_count": ref_counts.get(policy.id, 0),
                "is_enabled": policy.is_enabled,
                "created_by": policy.created_by,
                "creator_name": creator_name,
                "created_at": policy.created_at,
                "updated_at": policy.updated_at,
                "schedule_config": policy.schedule_config or {},
                "max_references": policy.max_references,
                "effective_max_references": max_refs,
                "last_triggered_at": policy.last_triggered_at,
                "next_trigger_at": policy.next_trigger_at,
                "last_status": policy.last_status,
                "last_summary": policy.last_summary or {},
            }
        else:
            item = {
                "id": policy.id,
                "name": policy.name,
                "is_enabled": policy.is_enabled,
            }
        data.append(item)
    response_data = {
        "items": data,
        "total": total,
        "enabled_total": enabled_total,
        "page": page,
        "page_size": page_size,
    }
    if is_manager(current_user):
        response_data["default_max_references"] = settings.SCHEDULE_POLICY_DEFAULT_MAX_REFERENCES
    return success_response(data=response_data)


@router.post("/")
async def create_schedule_policy(
    data: SchedulePolicyIn,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    next_time = _validate_policy_data(data)
    existing = await db.execute(
        select(SchedulePolicy).where(SchedulePolicy.name == data.name, SchedulePolicy.is_deleted == False)
    )
    if existing.scalar_one_or_none():
        raise UnifiedException(code=400, message="执行策略名称已存在")
    await _ensure_no_enabled_time_conflict(db, data)

    policy = SchedulePolicy(
        **data.model_dump(),
        next_trigger_at=next_time if data.is_enabled else None,
        created_by=current_user.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    await _audit_policy_operation(db, current_user, "创建", policy, "创建执行策略")
    return success_response(data=policy, message="执行策略创建成功")


@router.put("/{policy_id}")
async def update_schedule_policy(
    policy_id: int,
    data: SchedulePolicyIn,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SchedulePolicy).where(SchedulePolicy.id == policy_id, SchedulePolicy.is_deleted == False))
    policy = result.scalar_one_or_none()
    if not policy:
        raise UnifiedException(code=400, message="执行策略不存在")
    existing = await db.execute(
        select(SchedulePolicy).where(
            SchedulePolicy.name == data.name,
            SchedulePolicy.id != policy_id,
            SchedulePolicy.is_deleted == False,
        )
    )
    if existing.scalar_one_or_none():
        raise UnifiedException(code=400, message="执行策略名称已存在")

    ref_counts = await _reference_count_map(db, [policy_id])
    effective_max = data.max_references or settings.SCHEDULE_POLICY_DEFAULT_MAX_REFERENCES
    if ref_counts.get(policy_id, 0) > effective_max:
        raise UnifiedException(code=400, message="最大引用次数不能小于当前引用数量")

    next_time = _validate_policy_data(data)
    await _ensure_no_enabled_time_conflict(db, data, policy_id)
    if policy.is_enabled and not data.is_enabled:
        result = await db.execute(
            select(ExecutionSet).where(
                ExecutionSet.schedule_policy_id == policy_id,
                ExecutionSet.is_deleted == False,
            )
        )
        for execution_set in result.scalars().all():
            execution_set.is_enabled = False
            execution_set.scheduler_status = "disabled"
            execution_set.next_scheduled_run_at = None
            execution_set.scheduler_started_at = None
    elif not policy.is_enabled and data.is_enabled:
        result = await db.execute(
            select(ExecutionSet).where(
                ExecutionSet.schedule_policy_id == policy_id,
                ExecutionSet.is_deleted == False,
            )
        )
        for execution_set in result.scalars().all():
            execution_set.is_enabled = True
            execution_set.scheduler_status = "idle"
            execution_set.scheduler_error = None
            execution_set.next_scheduled_run_at = next_time
    for field, value in data.model_dump().items():
        setattr(policy, field, value)
    policy.next_trigger_at = next_time if data.is_enabled else None
    if not data.is_enabled:
        policy.last_status = "disabled"
    await db.commit()
    await db.refresh(policy)
    await _audit_policy_operation(db, current_user, "编辑", policy, "编辑执行策略")
    return success_response(data=policy, message="执行策略更新成功")


@router.delete("/{policy_id}")
async def delete_schedule_policy(
    policy_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SchedulePolicy).where(SchedulePolicy.id == policy_id, SchedulePolicy.is_deleted == False))
    policy = result.scalar_one_or_none()
    if not policy:
        raise UnifiedException(code=400, message="执行策略不存在")
    result = await db.execute(
        select(ExecutionSet).where(
            ExecutionSet.schedule_policy_id == policy_id,
            ExecutionSet.is_deleted == False,
        )
    )
    referenced_execution_sets = result.scalars().all()
    for execution_set in referenced_execution_sets:
        execution_set.schedule_policy_id = None
        execution_set.cron_expression = None
        execution_set.is_enabled = False
        execution_set.scheduler_status = "disabled"
        execution_set.next_scheduled_run_at = None
        execution_set.scheduler_started_at = None
    policy.is_deleted = True
    policy.deleted_at = beijing_now()
    policy.is_enabled = False
    policy.next_trigger_at = None
    await db.commit()
    await _audit_policy_operation(db, current_user, "删除", policy, "删除执行策略")
    return success_response(message="执行策略已删除")


@router.get("/{policy_id}/references")
async def list_policy_references(
    policy_id: int,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    policy = await db.get(SchedulePolicy, policy_id)
    if not policy or policy.is_deleted:
        raise UnifiedException(code=400, message="执行策略不存在")
    result = await db.execute(
        select(ExecutionSet, Project.name.label("project_name"))
        .join(Project, ExecutionSet.project_id == Project.id)
        .where(
            ExecutionSet.schedule_policy_id == policy_id,
            ExecutionSet.is_deleted == False,
            Project.is_deleted == False,
        )
        .order_by(Project.name, ExecutionSet.id)
    )
    items = result.all()
    return success_response(data=[{
        "id": execution_set.id,
        "name": execution_set.name,
        "project_id": execution_set.project_id,
        "project_name": project_name,
        "scheduler_status": execution_set.scheduler_status,
        "last_scheduled_run_at": execution_set.last_scheduled_run_at,
        "next_scheduled_run_at": execution_set.next_scheduled_run_at,
    } for execution_set, project_name in items])


@router.get("/{policy_id}/logs")
async def list_policy_logs(
    policy_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    execution_set_name: str | None = None,
    project_name: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    current_user: User = Depends(check_manager_permission),
    db: AsyncSession = Depends(get_db),
):
    policy = await db.get(SchedulePolicy, policy_id)
    if not policy or policy.is_deleted:
        raise UnifiedException(code=400, message="执行策略不存在")

    conditions = [
        ScheduleRunLog.policy_id == policy_id,
        ScheduleRunLog.is_deleted == False,
    ]
    if execution_set_name:
        conditions.append(ExecutionSet.name.contains(execution_set_name))
    if project_name:
        conditions.append(Project.name.contains(project_name))
    if start_time:
        conditions.append(ScheduleRunLog.triggered_at >= start_time.replace(tzinfo=None))
    if end_time:
        conditions.append(ScheduleRunLog.triggered_at <= end_time.replace(tzinfo=None))

    base_query = (
        select(
            ScheduleRunLog,
            ExecutionSet.name.label("execution_set_name"),
            Project.name.label("project_name"),
        )
        .outerjoin(ExecutionSet, ScheduleRunLog.execution_set_id == ExecutionSet.id)
        .outerjoin(Project, ExecutionSet.project_id == Project.id)
        .where(*conditions)
    )
    total_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = total_result.scalar() or 0
    result = await db.execute(
        base_query
        .order_by(ScheduleRunLog.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()
    return success_response(data={
        "items": [{
            "id": log.id,
            "policy_id": log.policy_id,
            "execution_set_id": log.execution_set_id,
            "execution_set_name": execution_set_name,
            "project_name": project_name,
            "report_id": log.report_id,
            "status": log.status,
            "message_status": log.message_status,
            "message_detail": log.message_detail,
            "triggered_at": log.triggered_at,
            "finished_at": log.finished_at,
        } for log, execution_set_name, project_name in rows],
        "total": total,
    })
