"""
Execution set management endpoints
"""
import logging
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Literal
from db.session import get_db, AsyncSessionLocal
from models.models import ExecutionSet, ExecutionItem, Project, Environment, User, Report, TestCase, ParameterSet, Interface, SchedulePolicy, SchedulePolicyBinding
from core.security import get_current_active_user
from core.response import mask_sensitive_data, success_response, UnifiedException
from core.config import settings
from core.timezone import beijing_now
from services.schedule_utils import schedule_text
from pydantic import BaseModel, Field
from datetime import datetime
from utils.audit_logger import (
    build_batch_audit_description,
    build_project_audit_description,
    log_operation,
    log_user_operation,
)
from core.permissions import ensure_project_access, ensure_project_asset_manage, ensure_project_detail_access, is_manager
from services.message_service import prepare_execution_notification_config, validate_execution_notification_config

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_execution_audit_description(project_name: str, action: str, execution_set_name: str) -> str:
    return build_project_audit_description(project_name, f"{action}：{execution_set_name}")


def _execution_report_summary(report: Report | None) -> dict:
    total = max(int(getattr(report, "total_cases", 0) or 0), 0)
    passed = max(int(getattr(report, "passed_cases", 0) or 0), 0)
    failed = max(int(getattr(report, "failed_cases", 0) or 0), 0)
    not_executed = max(total - passed - failed, 0)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "not_executed": not_executed,
    }


def _execution_audit_status(report: Report | None) -> str:
    """Keep the final execution audit status aligned with the persisted report."""
    return "success" if getattr(report, "status", None) == "success" else "failed"


def _build_execution_result_audit_description(
    project_name: str,
    execution_set_name: str,
    report: Report | None,
) -> str:
    summary = _execution_report_summary(report)
    return build_project_audit_description(
        project_name,
        (
            f"执行集「{execution_set_name}」执行结果："
            f"成功{summary['passed']}，失败{summary['failed']}，"
            f"未执行{summary['not_executed']}，共计{summary['total']}"
        ),
    )


def _execution_set_payload(execution_set: ExecutionSet, current_user: User) -> dict:
    """组装执行集基础数据，避免普通用户拿到通知配置中的敏感值。"""
    payload = {
        column.name: getattr(execution_set, column.name)
        for column in execution_set.__table__.columns
    }
    if not is_manager(current_user):
        payload["notification_config"] = mask_sensitive_data(payload.get("notification_config") or {})
    return payload


async def _ensure_project_manage_permission(db: AsyncSession, project_id: int, current_user: User) -> Project:
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    return project


async def _ensure_execution_set_manage_permission(db: AsyncSession, execution_set: ExecutionSet, current_user: User) -> Project:
    return await _ensure_project_manage_permission(db, execution_set.project_id, current_user)


async def _sync_api_schedule_binding(
    db: AsyncSession,
    execution_set_id: int,
    schedule_policy_id: int | None,
    current_user_id: int | None = None,
) -> None:
    result = await db.execute(
        select(SchedulePolicyBinding).where(
            SchedulePolicyBinding.module == "api_test",
            SchedulePolicyBinding.target_type == "execution_set",
            SchedulePolicyBinding.target_id == execution_set_id,
            SchedulePolicyBinding.is_deleted == False,
        )
    )
    binding = result.scalar_one_or_none()
    if schedule_policy_id:
        if binding is None:
            db.add(SchedulePolicyBinding(
                policy_id=schedule_policy_id,
                module="api_test",
                target_type="execution_set",
                target_id=execution_set_id,
                is_enabled=True,
                created_by=current_user_id,
            ))
        else:
            binding.policy_id = schedule_policy_id
            binding.is_enabled = True
    elif binding is not None:
        binding.is_enabled = False
        binding.is_deleted = True
        binding.deleted_at = beijing_now()


async def _validate_execution_resources(
    db: AsyncSession,
    project_id: int,
    environment_id: int | None,
    parameter_set_id: int | None,
    schedule_policy_id: int | None,
    execution_items: list | None,
    current_execution_set_id: int | None = None, allow_disabled_schedule_policy: bool = False,
):
    if environment_id is None:
        raise UnifiedException(code=400, message="请配置或者选择运行环境")

    env_result = await db.execute(
        select(Environment).where(
            Environment.id == environment_id,
            Environment.project_id == project_id,
            Environment.is_deleted == False
        )
    )
    if not env_result.scalar_one_or_none():
        raise UnifiedException(code=400, message="运行环境不属于当前项目或不存在")

    if parameter_set_id is not None:
        ps_result = await db.execute(
            select(ParameterSet).where(
                ParameterSet.id == parameter_set_id,
                ParameterSet.project_id == project_id,
                ParameterSet.is_deleted == False
            )
        )
        if not ps_result.scalar_one_or_none():
            raise UnifiedException(code=400, message="参数集不属于当前项目或不存在")

    if schedule_policy_id is not None:
        policy_result = await db.execute(
            select(SchedulePolicy).where(
                SchedulePolicy.id == schedule_policy_id,
                SchedulePolicy.is_deleted == False,
            )
        )
        policy = policy_result.scalar_one_or_none()
        if not policy or (not policy.is_enabled and not allow_disabled_schedule_policy):
            raise UnifiedException(code=400, message="执行策略不存在或已停用")
        max_refs = policy.max_references or settings.SCHEDULE_POLICY_DEFAULT_MAX_REFERENCES
        count_query = select(func.count()).select_from(ExecutionSet).where(
            ExecutionSet.schedule_policy_id == schedule_policy_id,
            ExecutionSet.is_deleted == False,
        )
        if current_execution_set_id:
            count_query = count_query.where(ExecutionSet.id != current_execution_set_id)
        ref_count = (await db.execute(count_query)).scalar() or 0
        if ref_count >= max_refs:
            raise UnifiedException(code=400, message=f"该执行策略最多允许 {max_refs} 个执行集引用")

    if execution_items:
        case_ids = [item.test_case_id if hasattr(item, "test_case_id") else item.get("test_case_id") for item in execution_items]
        case_ids = [cid for cid in case_ids if cid is not None]
        if len(case_ids) != len(set(case_ids)):
            raise UnifiedException(code=400, message="执行集不能重复选择同一个用例")
        result = await db.execute(
            select(TestCase.id).join(Interface, TestCase.interface_id == Interface.id).where(
                TestCase.id.in_(case_ids),
                TestCase.project_id == project_id,
                TestCase.is_deleted == False,
                Interface.is_deleted == False,
            )
        )
        found_ids = set(result.scalars().all())
        missing = [cid for cid in case_ids if cid not in found_ids]
        if missing:
            raise UnifiedException(code=400, message=f"存在不属于当前项目或不存在的用例: {missing[:5]}")


class ExecutionItemCreate(BaseModel):
    """执行项创建模型"""
    test_case_id: int
    order: int


class ExecutionSetCreate(BaseModel):
    """执行集创建模型"""
    name: str
    description: str | None = None
    project_id: int
    environment_id: int | None = None
    parameter_set_id: int | None = None
    schedule_policy_id: int | None = None
    retry_count: int = Field(default=0, ge=0, le=3)
    cron_expression: str | None = None
    is_enabled: bool = True
    notification_config: dict = Field(default_factory=dict)
    execution_mode: Literal["serial", "parallel"] = "serial"
    execution_items: List[ExecutionItemCreate] = []


class ExecutionSetUpdate(BaseModel):
    """执行集更新模型"""
    name: str | None = None
    description: str | None = None
    environment_id: int | None = None
    parameter_set_id: int | None = None
    schedule_policy_id: int | None = None
    retry_count: int | None = Field(default=None, ge=0, le=3)
    cron_expression: str | None = None
    is_enabled: bool | None = None
    notification_config: dict | None = None
    execution_mode: Literal["serial", "parallel"] | None = None
    execution_items: List[ExecutionItemCreate] | None = None


class ExecutionSetResponse(BaseModel):
    """执行集响应模型"""
    id: int
    name: str
    description: str | None = None
    project_id: int
    environment_id: int
    parameter_set_id: int | None = None
    schedule_policy_id: int | None = None
    retry_count: int
    cron_expression: str | None = None
    is_enabled: bool
    notification_config: dict
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


@router.get("/")
async def list_execution_sets(
    project_id: int,
    name: str | None = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定项目的执行集列表（含统计信息）"""
    project_result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)

    query = select(ExecutionSet).where(ExecutionSet.project_id == project_id, ExecutionSet.is_deleted == False)
    count_query = select(func.count()).select_from(ExecutionSet).where(ExecutionSet.project_id == project_id, ExecutionSet.is_deleted == False)
    if name:
        query = query.where(ExecutionSet.name.contains(name))
        count_query = count_query.where(ExecutionSet.name.contains(name))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    query = query.order_by(ExecutionSet.created_at.desc(), ExecutionSet.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    execution_sets = result.scalars().all()

    # 批量查询每个执行集的用例数
    case_counts = {}
    param_set_names = {}
    schedule_policy_map = {}
    if execution_sets:
        set_ids = [es.id for es in execution_sets]
        count_result = await db.execute(
            select(ExecutionItem.execution_set_id, func.count(ExecutionItem.id))
            .join(TestCase, ExecutionItem.test_case_id == TestCase.id)
            .join(Interface, TestCase.interface_id == Interface.id)
            .where(
                ExecutionItem.execution_set_id.in_(set_ids),
                ExecutionItem.is_deleted == False,
                TestCase.is_deleted == False,
                Interface.is_deleted == False,
            )
            .group_by(ExecutionItem.execution_set_id)
        )
        case_counts = {row[0]: row[1] for row in count_result.all()}

        # 批量查询参数集名称
        ps_ids = list(set(es.parameter_set_id for es in execution_sets if es.parameter_set_id))
        if ps_ids:
            ps_result = await db.execute(
                select(ParameterSet.id, ParameterSet.name).where(ParameterSet.id.in_(ps_ids))
            )
            param_set_names = {row[0]: row[1] for row in ps_result.all()}

        policy_ids = list(set(es.schedule_policy_id for es in execution_sets if es.schedule_policy_id))
        if policy_ids:
            policy_result = await db.execute(select(SchedulePolicy).where(SchedulePolicy.id.in_(policy_ids)))
            schedule_policy_map = {policy.id: policy for policy in policy_result.scalars().all()}

    # 批量查询每个执行集的最新报告
    last_reports = {}
    if execution_sets:
        # 子查询：每个执行集的最新报告ID（排除已删除）
        latest_subq = (
            select(Report.execution_set_id, func.max(Report.id).label('max_id'))
            .where(Report.execution_set_id.in_(set_ids), Report.is_deleted == False)
            .group_by(Report.execution_set_id)
            .subquery()
        )
        report_result = await db.execute(
            select(Report)
            .join(latest_subq, Report.id == latest_subq.c.max_id)
            .where(Report.is_deleted == False)
        )
        for r in report_result.scalars().all():
            last_reports[r.execution_set_id] = r

    data = []
    for es in execution_sets:
        report = last_reports.get(es.id)
        policy = schedule_policy_map.get(es.schedule_policy_id)
        data.append({
            "id": es.id,
            "name": es.name,
            "description": es.description,
            "project_id": es.project_id,
            "environment_id": es.environment_id,
            "parameter_set_id": es.parameter_set_id,
            "parameter_set_name": param_set_names.get(es.parameter_set_id) if es.parameter_set_id else None,
            "schedule_policy_id": es.schedule_policy_id,
            "schedule_policy_name": policy.name if policy else None,
            "schedule_policy_text": (
                schedule_text(policy.schedule_type, policy.schedule_config, policy.cron_expression)
                if policy and is_manager(current_user) else None
            ),
            "schedule_policy_enabled": policy.is_enabled if policy else None,
            "retry_count": es.retry_count,
            "cron_expression": es.cron_expression if is_manager(current_user) else None,
            "is_enabled": es.is_enabled,
            "scheduler_status": es.scheduler_status,
            "last_scheduled_run_at": es.last_scheduled_run_at,
            "next_scheduled_run_at": es.next_scheduled_run_at,
            "notification_config": (
                es.notification_config
                if is_manager(current_user)
                else mask_sensitive_data(es.notification_config or {})
            ),
            "execution_mode": es.execution_mode or "serial",
            "created_at": es.created_at,
            "updated_at": es.updated_at,
            "case_count": case_counts.get(es.id, 0),
            "last_passed": report.passed_cases if report else 0,
            "last_failed": report.failed_cases if report else 0,
            "last_status": report.status if report else None,
            "last_report_id": report.id if report else None,
        })

    return success_response(data={"items": data, "total": total})


@router.post("/")
async def create_execution_set(
    execution_set_data: ExecutionSetCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新执行集"""
    # 验证项目和环境是否存在
    project = await _ensure_project_manage_permission(db, execution_set_data.project_id, current_user)

    # 检查同项目下名称是否重复
    existing = (await db.execute(
        select(ExecutionSet).where(
            ExecutionSet.project_id == execution_set_data.project_id,
            ExecutionSet.name == execution_set_data.name,
            ExecutionSet.is_deleted == False
        )
    )).scalars().first()
    if existing:
        raise UnifiedException(code=400, message="该项目下执行集名称已存在")

    await _validate_execution_resources(
        db,
        execution_set_data.project_id,
        execution_set_data.environment_id,
        execution_set_data.parameter_set_id,
        execution_set_data.schedule_policy_id,
        execution_set_data.execution_items,
    )
    notification_config = await validate_execution_notification_config(db, execution_set_data.notification_config, automatic=execution_set_data.schedule_policy_id is not None)

    db_execution_set = ExecutionSet(
        name=execution_set_data.name,
        description=execution_set_data.description,
        project_id=execution_set_data.project_id,
        environment_id=execution_set_data.environment_id,
        parameter_set_id=execution_set_data.parameter_set_id,
        schedule_policy_id=execution_set_data.schedule_policy_id,
        retry_count=execution_set_data.retry_count,
        cron_expression=None,
        is_enabled=bool(execution_set_data.schedule_policy_id),
        scheduler_status="idle" if execution_set_data.schedule_policy_id else "disabled",
        notification_config=notification_config,
        execution_mode=execution_set_data.execution_mode or "serial",
    )
    
    db.add(db_execution_set)
    await db.flush()  # 获取execution_set的ID
    
    # 添加执行项
    for item_data in execution_set_data.execution_items:
        db_item = ExecutionItem(
            execution_set_id=db_execution_set.id,
            test_case_id=item_data.test_case_id,
            order=item_data.order,
        )
        db.add(db_item)
    await _sync_api_schedule_binding(
        db,
        db_execution_set.id,
        execution_set_data.schedule_policy_id,
        current_user.id,
    )
    
    await db.commit()
    await db.refresh(db_execution_set)
    
    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="execution",
        operation="create",
        target_id=db_execution_set.id,
        target_name=db_execution_set.name,
        description=build_batch_audit_description(
            project.name,
            "创建",
            "执行集",
            1,
            {"执行项": len(execution_set_data.execution_items)},
        ),
    )
    
    return success_response(data=_execution_set_payload(db_execution_set, current_user), message="执行集创建成功")


@router.get("/{execution_set_id}")
async def get_execution_set(
    execution_set_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定执行集信息（含执行项）"""
    result = await db.execute(select(ExecutionSet).where(ExecutionSet.id == execution_set_id, ExecutionSet.is_deleted == False))
    execution_set = result.scalar_one_or_none()

    if not execution_set:
        raise UnifiedException(code=400, message="执行集不存在")
    project_result = await db.execute(select(Project).where(Project.id == execution_set.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    ensure_project_detail_access(current_user, project)

    # 加载执行项
    result = await db.execute(
        select(ExecutionItem)
        .join(TestCase, ExecutionItem.test_case_id == TestCase.id)
        .join(Interface, TestCase.interface_id == Interface.id)
        .where(ExecutionItem.execution_set_id == execution_set_id, ExecutionItem.is_deleted == False)
        .where(TestCase.is_deleted == False, Interface.is_deleted == False)
        .order_by(ExecutionItem.order)
    )
    items = result.scalars().all()

    return success_response(data={
        "id": execution_set.id,
        "name": execution_set.name,
        "description": execution_set.description,
        "project_id": execution_set.project_id,
        "environment_id": execution_set.environment_id,
        "parameter_set_id": execution_set.parameter_set_id,
        "schedule_policy_id": execution_set.schedule_policy_id,
        "retry_count": execution_set.retry_count,
        "cron_expression": execution_set.cron_expression,
        "is_enabled": execution_set.is_enabled,
        "scheduler_status": execution_set.scheduler_status,
        "last_scheduled_run_at": execution_set.last_scheduled_run_at,
        "next_scheduled_run_at": execution_set.next_scheduled_run_at,
        "notification_config": (
            execution_set.notification_config
            if is_manager(current_user)
            else mask_sensitive_data(execution_set.notification_config or {})
        ),
        "execution_mode": execution_set.execution_mode or "serial",
        "created_at": execution_set.created_at,
        "updated_at": execution_set.updated_at,
        "execution_items": [
            {
                "id": item.id,
                "test_case_id": item.test_case_id,
                "order": item.order,
            }
            for item in items
        ],
    })


@router.put("/{execution_set_id}")
async def update_execution_set(
    execution_set_id: int,
    execution_set_data: ExecutionSetUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新执行集信息"""
    result = await db.execute(select(ExecutionSet).where(ExecutionSet.id == execution_set_id, ExecutionSet.is_deleted == False))
    execution_set = result.scalar_one_or_none()

    if not execution_set:
        raise UnifiedException(code=400, message="执行集不存在")
    project = await _ensure_execution_set_manage_permission(db, execution_set, current_user)

    # 如果修改了名称，检查同项目下是否重复
    if execution_set_data.name and execution_set_data.name != execution_set.name:
        existing = (await db.execute(
            select(ExecutionSet).where(
                ExecutionSet.project_id == execution_set.project_id,
                ExecutionSet.name == execution_set_data.name,
                ExecutionSet.is_deleted == False
            )
        )).scalars().first()
        if existing:
            raise UnifiedException(code=400, message="该项目下执行集名称已存在")

    incoming = execution_set_data.model_dump(exclude_unset=True)
    if "environment_id" in incoming and incoming["environment_id"] is None:
        raise UnifiedException(code=400, message="请配置或者选择运行环境")
    next_schedule_policy_id = (
        incoming["schedule_policy_id"]
        if "schedule_policy_id" in incoming
        else execution_set.schedule_policy_id
    )
    incoming["notification_config"] = await prepare_execution_notification_config(db, execution_set.notification_config, incoming, current_automatic=bool(execution_set.schedule_policy_id), automatic=next_schedule_policy_id is not None)

    # 更新字段
    await _validate_execution_resources(
        db,
        execution_set.project_id,
        incoming.get("environment_id", execution_set.environment_id),
        execution_set_data.parameter_set_id if execution_set_data.parameter_set_id is not None else execution_set.parameter_set_id,
        next_schedule_policy_id,
        execution_set_data.execution_items,
        current_execution_set_id=execution_set_id,
        allow_disabled_schedule_policy=(next_schedule_policy_id is not None and next_schedule_policy_id == execution_set.schedule_policy_id),
    )

    update_data = incoming
    items_data = update_data.pop('execution_items', None)
    execution_item_count = len(items_data) if items_data is not None else None
    if "schedule_policy_id" in update_data:
        policy_id = update_data.get("schedule_policy_id")
        update_data["cron_expression"] = None
        update_data["is_enabled"] = bool(policy_id)
        update_data["scheduler_status"] = "idle" if policy_id else "disabled"
        update_data["next_scheduled_run_at"] = None
    for field, value in update_data.items():
        setattr(execution_set, field, value)

    # 如果传了 execution_items，软删除旧项并创建新项
    if items_data is not None:
        now = beijing_now()
        old_items = await db.execute(
            select(ExecutionItem).where(ExecutionItem.execution_set_id == execution_set_id)
        )
        for old in old_items.scalars().all():
            old.is_deleted = True
            old.deleted_at = now
        for item_data in items_data:
            db_item = ExecutionItem(
                execution_set_id=execution_set_id,
                test_case_id=item_data['test_case_id'],
                order=item_data['order'],
            )
            db.add(db_item)
    if "schedule_policy_id" in incoming:
        await _sync_api_schedule_binding(
            db,
            execution_set_id,
            incoming.get("schedule_policy_id"),
            current_user.id,
        )

    await db.commit()
    await db.refresh(execution_set)

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="execution",
        operation="update",
        target_id=execution_set.id,
        target_name=execution_set.name,
        description=(
            build_batch_audit_description(
                project.name,
                "更新",
                "执行集",
                1,
                {"执行项": execution_item_count},
            )
            if execution_item_count is not None
            else build_project_audit_description(project.name, f"更新执行集：{execution_set.name}")
        ),
    )

    return success_response(data=_execution_set_payload(execution_set, current_user), message="执行集更新成功")


@router.post("/{execution_set_id}/run")
async def run_execution_set(
    execution_set_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """触发执行集（异步后台执行）"""
    # 验证执行集存在
    result = await db.execute(select(ExecutionSet).where(ExecutionSet.id == execution_set_id, ExecutionSet.is_deleted == False))
    execution_set = result.scalar_one_or_none()

    if not execution_set:
        raise UnifiedException(code=400, message="执行集不存在")
    project = await _ensure_execution_set_manage_permission(db, execution_set, current_user)

    # 验证是否有关联用例
    result = await db.execute(
        select(ExecutionItem)
        .join(TestCase, ExecutionItem.test_case_id == TestCase.id)
        .join(Interface, TestCase.interface_id == Interface.id)
        .where(
            ExecutionItem.execution_set_id == execution_set_id,
            ExecutionItem.is_deleted == False,
            TestCase.is_deleted == False,
            Interface.is_deleted == False,
        )
    )
    if not result.scalars().all():
        raise UnifiedException(code=400, message="执行集中没有关联的用例")

    env_result = await db.execute(
        select(Environment).where(
            Environment.id == execution_set.environment_id,
            Environment.is_deleted == False,
        )
    )
    if not env_result.scalar_one_or_none():
        raise UnifiedException(code=400, message="运行环境不存在")

    report = Report(
        name=f"{execution_set.name}-{beijing_now().strftime('%Y%m%d_%H%M%S')}",
        project_id=execution_set.project_id,
        execution_set_id=execution_set.id,
        status="running",
        execution_mode=execution_set.execution_mode or "serial",
        start_time=beijing_now(),
        total_steps=0,
        passed_steps=0,
        failed_steps=0,
        total_cases=0,
        passed_cases=0,
        failed_cases=0,
        pass_rate=0.0,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    execution_set_name = execution_set.name
    await log_user_operation(
        db=db,
        user=current_user,
        module="execution",
        operation="执行",
        target_id=execution_set.id,
        target_name=execution_set_name,
        description=_build_execution_audit_description(project.name, "触发执行集", execution_set_name),
        details={"status": "queued", "report_id": report.id, "project_name": project.name},
    )

    project_name = project.name

    async def run_in_background(report_id: int):
        from services.execution_engine import execute_execution_set
        async with AsyncSessionLocal() as bg_db:
            try:
                await execute_execution_set(execution_set_id, bg_db, report_id=report_id)
                logger.info(f"Execution completed, report_id={report_id}")
                completed_report = await bg_db.get(Report, report_id)
                result_summary = _execution_report_summary(completed_report)
                audit_status = _execution_audit_status(completed_report)
                await log_user_operation(
                    db=bg_db,
                    user=current_user,
                    module="execution",
                    operation="执行",
                    target_id=execution_set_id,
                    target_name=execution_set_name,
                    description=_build_execution_result_audit_description(
                        project_name,
                        execution_set_name,
                        completed_report,
                    ),
                    details={
                        "status": audit_status,
                        "report_id": report_id,
                        "project_name": project_name,
                        **result_summary,
                    },
                )
            except Exception as e:
                logger.exception(f"Background execution failed: {e}")
                failed_report = await bg_db.get(Report, report_id)
                if failed_report:
                    failed_report.status = "failed"
                    failed_report.end_time = beijing_now()
                    failed_report.duration = 0
                    await bg_db.commit()
                await log_user_operation(
                    db=bg_db,
                    user=current_user,
                    module="execution",
                    operation="执行",
                    target_id=execution_set_id,
                    target_name=execution_set_name,
                    description=_build_execution_audit_description(project_name, "执行集失败", execution_set_name),
                    details={"status": "failed", "report_id": report_id, "project_name": project_name},
                )

    asyncio.create_task(run_in_background(report.id))

    return success_response(data={"report_id": report.id}, message="执行已触发，请查看测试报告")


@router.delete("/{execution_set_id}")
async def delete_execution_set(
    execution_set_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """删除执行集（软删除）"""
    from models.models import Report, ExecutionItem
    result = await db.execute(select(ExecutionSet).where(ExecutionSet.id == execution_set_id, ExecutionSet.is_deleted == False))
    execution_set = result.scalar_one_or_none()

    if not execution_set:
        raise UnifiedException(code=400, message="执行集不存在")
    project = await _ensure_execution_set_manage_permission(db, execution_set, current_user)

    # 解除关联报告的执行集引用
    rpt_result = await db.execute(select(Report).where(Report.execution_set_id == execution_set_id))
    for rpt in rpt_result.scalars().all():
        rpt.execution_set_id = None

    # 软删除执行项
    now = beijing_now()
    item_result = await db.execute(select(ExecutionItem).where(ExecutionItem.execution_set_id == execution_set_id))
    for item in item_result.scalars().all():
        item.is_deleted = True
        item.deleted_at = now

    execution_set.is_deleted = True
    execution_set.deleted_at = now
    await db.commit()

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="execution",
        operation="delete",
        target_id=execution_set.id,
        target_name=execution_set.name,
        description=build_project_audit_description(project.name, f"删除执行集：{execution_set.name}"),
    )

    return success_response(message="执行集删除成功")


class BatchDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/batch-delete")
async def batch_delete_execution_sets(
    req: BatchDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """批量删除执行集（级联软删除）"""
    if not req.ids:
        raise UnifiedException(code=400, message="请选择要删除的执行集")

    from models.models import Report, ExecutionItem
    now = beijing_now()
    deleted = 0
    execution_sets = []
    projects_by_id: dict[int, Project] = {}

    for es_id in dict.fromkeys(req.ids):
        result = await db.execute(
            select(ExecutionSet).where(ExecutionSet.id == es_id, ExecutionSet.is_deleted == False)
        )
        es = result.scalar_one_or_none()
        if not es:
            continue
        projects_by_id[es.project_id] = await _ensure_project_manage_permission(db, es.project_id, current_user)
        execution_sets.append(es)

    delete_audits: dict[int, dict[str, int | str]] = {}
    for es in execution_sets:
        es_id = es.id
        rpt_result = await db.execute(select(Report).where(Report.execution_set_id == es_id))
        reports = list(rpt_result.scalars().all())
        for rpt in reports:
            rpt.execution_set_id = None

        item_result = await db.execute(select(ExecutionItem).where(ExecutionItem.execution_set_id == es_id))
        execution_items = list(item_result.scalars().all())
        for item in execution_items:
            item.is_deleted = True
            item.deleted_at = now

        es.is_deleted = True
        es.deleted_at = now
        deleted += 1
        audit = delete_audits.setdefault(
            es.project_id,
            {
                "project_name": projects_by_id[es.project_id].name,
                "execution_set_count": 0,
                "report_count": 0,
                "execution_item_count": 0,
            },
        )
        audit["execution_set_count"] += 1
        audit["report_count"] += len(reports)
        audit["execution_item_count"] += len(execution_items)

    await db.commit()

    for project_id, audit in delete_audits.items():
        description = build_batch_audit_description(
            str(audit["project_name"]),
            "删除",
            "执行集",
            int(audit["execution_set_count"]),
            {
                "执行项": int(audit["execution_item_count"]),
                "报告": int(audit["report_count"]),
            },
        )
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="execution",
            operation="delete",
            target_id=project_id,
            target_name=str(audit["project_name"]),
            description=description,
            details={
                "execution_set_count": int(audit["execution_set_count"]),
                "execution_item_count": int(audit["execution_item_count"]),
                "report_count": int(audit["report_count"]),
            },
        )

    return success_response(data={"deleted": deleted}, message=f"成功删除 {deleted} 个执行集")
