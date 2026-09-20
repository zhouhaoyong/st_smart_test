"""测试工作台各资源域共用的校验器与审计工具。"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from db.session import AsyncSessionLocal
from models.models import (
    TWBugRecord,
    TWRequirement,
    TWSystem,
    TWTestCase,
    TWTestExecution,
    TWVersion,
    User,
)
from models.models_workbench import TWCompletedRequirement, TWMergedRequirement, TWProject
from services.test_workbench_service import (
    assert_same_workbench_scope,
    get_merged_requirement,
    get_requirement,
    get_test_case,
    get_version,
)
from services.test_workbench_service.records import ensure_scoped_unique_value
from services.test_workbench_audit import build_change_details, snapshot_workbench_record
from utils.audit_logger import (
    build_batch_audit_description,
    build_project_audit_description,
    log_operation,
)


def _dump_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _workbench_target_name(record: object) -> str:
    return str(
        getattr(record, "name", None)
        or getattr(record, "version_no", None)
        or getattr(record, "title", None)
        or f"#{getattr(record, 'id', '')}"
    )


async def _workbench_project_name(db: AsyncSession, record: object) -> str:
    """获取工作台资源所属项目名称；项目资源自身直接使用其名称。"""
    project_id = getattr(record, "project_id", None)
    if project_id is None and isinstance(record, TWProject):
        return str(getattr(record, "name", None) or "未指定")
    if not project_id:
        return "未指定"
    result = await db.execute(
        select(TWProject.name).where(TWProject.id == project_id, TWProject.is_deleted == False)
    )
    return str(result.scalar_one_or_none() or "未指定")


async def _workbench_ai_project_name(
    db: AsyncSession,
    *,
    asset_name: str,
    target_id: int | None,
    target_name: str | None,
) -> str:
    """根据 AI 审计对象反查项目，兼容追问阶段的临时对象。"""
    if not target_id:
        return "未指定"
    candidates: list[tuple[type, str]] = []
    if asset_name == "合并需求":
        candidates = [(TWVersion, "version_no"), (TWMergedRequirement, "title")]
    elif asset_name == "需求":
        candidates = [(TWRequirement, "title"), (TWCompletedRequirement, "title"), (TWMergedRequirement, "title")]
    elif asset_name == "测试用例":
        candidates = [(TWProject, "name"), (TWRequirement, "title"), (TWCompletedRequirement, "title"), (TWMergedRequirement, "title")]
    else:
        candidates = [(TWProject, "name")]
    try:
        for model, name_field in candidates:
            field = getattr(model, name_field)
            conditions = [model.id == target_id, model.is_deleted == False]
            if target_name:
                conditions.append(field == target_name)
            result = await db.execute(select(model).where(*conditions))
            record = result.scalar_one_or_none()
            if record is not None:
                return await _workbench_project_name(db, record)
        return "未指定"
    except Exception:
        return "未指定"


async def ensure_project_unique_value(
    db: AsyncSession,
    model: type,
    project_id: int,
    field_name: str,
    value: str | None,
    label: str,
    exclude_id: int | None = None,
) -> None:
    """Ensure an active workbench record has a project-scoped unique value."""
    await ensure_scoped_unique_value(
        db,
        model,
        scope_field="project_id",
        scope_id=project_id,
        field_name=field_name,
        value=value,
        label=label,
        scope_label="项目",
        exclude_id=exclude_id,
    )


async def ensure_system_unique_value(
    db: AsyncSession,
    model: type,
    system_id: int,
    field_name: str,
    value: str | None,
    label: str,
    exclude_id: int | None = None,
) -> None:
    """Ensure an active workbench record has a system-scoped unique value."""
    await ensure_scoped_unique_value(
        db,
        model,
        scope_field="system_id",
        scope_id=system_id,
        field_name=field_name,
        value=value,
        label=label,
        scope_label="系统",
        exclude_id=exclude_id,
    )


async def _audit_workbench_mutation(
    db: AsyncSession,
    current_user: User,
    *,
    operation: str,
    asset_name: str,
    record: object,
    before: dict | None = None,
    description: str | None = None,
) -> None:
    after = snapshot_workbench_record(record)
    details = build_change_details(before, after) if before is not None else {"after": after}
    project_name = await _workbench_project_name(db, record)
    audit_content = description or f"{operation}{asset_name}：{_workbench_target_name(record)}"
    audit_description = (
        audit_content
        if isinstance(record, TWProject)
        else build_project_audit_description(project_name, audit_content)
    )
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=getattr(current_user, "real_name", "") or getattr(current_user, "nick_name", "") or "未知用户",
        module="test_workbench",
        operation=operation,
        target_id=getattr(record, "id", None),
        target_name=_workbench_target_name(record),
        description=audit_description,
        details=details,
    )


async def _audit_workbench_batch_mutation(
    db: AsyncSession,
    current_user: User,
    *,
    project: object,
    operation: str,
    asset_name: str,
    primary_count: int,
    related_counts: dict[str, int] | None = None,
    details: dict | None = None,
) -> None:
    """为一次工作台批量请求写一条汇总审计，不保存逐条快照。"""
    project_name = str(getattr(project, "name", None) or "未指定")
    audit_details = dict(details or {})
    audit_details.setdefault("count", primary_count)
    if related_counts:
        audit_details.setdefault("related_counts", dict(related_counts))
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=getattr(current_user, "real_name", "") or getattr(current_user, "nick_name", "") or "未知用户",
        module="test_workbench",
        operation=operation,
        target_id=getattr(project, "id", None),
        target_name=project_name,
        description=build_batch_audit_description(
            project_name,
            operation,
            asset_name,
            primary_count,
            related_counts,
        ),
        details=audit_details,
    )


async def _audit_workbench_ai_operation(
    current_user: User,
    *,
    operation: str,
    asset_name: str,
    target_id: int | None,
    target_name: str,
    description: str,
    outcome: str = "成功",
) -> None:
    """为流式 AI 成功操作补充审计，不复用已结束的请求级会话。"""
    async with AsyncSessionLocal() as audit_db:
        project_name = await _workbench_ai_project_name(
            audit_db,
            asset_name=asset_name,
            target_id=target_id,
            target_name=target_name,
        )
        audit_content = f"{description or f'{operation}{asset_name}：{target_name}'}：{outcome}"
        await log_operation(
            db=audit_db,
            user_id=current_user.id,
            user_name=getattr(current_user, "real_name", "") or getattr(current_user, "nick_name", "") or "未知用户",
            module="test_workbench",
            operation=operation,
            target_id=target_id,
            target_name=target_name,
            description=build_project_audit_description(project_name, audit_content),
        )


async def _validate_requirement_relation(
    db: AsyncSession,
    current_user: User,
    requirement_id: int | None,
    version: TWVersion,
) -> None:
    """关联资产只能绑定当前项目、系统和版本下的有效需求。"""
    if requirement_id is None:
        return
    requirement = await get_requirement(db, requirement_id, current_user)
    if (
        requirement.project_id != version.project_id
        or requirement.system_id != version.system_id
        or requirement.version_id != version.id
    ):
        raise UnifiedException(code=400, message="关联需求必须属于当前系统和版本")


async def _validate_merged_requirement_relation(
    db: AsyncSession,
    current_user: User,
    merged_requirement_id: int | None,
    version: TWVersion,
) -> None:
    """关联合并需求只能绑定当前系统版本下的有效合并需求（血缘弱关联）。"""
    if merged_requirement_id is None:
        return
    merged = await get_merged_requirement(db, merged_requirement_id, current_user)
    assert_same_workbench_scope(version, merged, "合并需求")


async def _validate_test_case_relation(
    db: AsyncSession,
    current_user: User,
    test_case_id: int | None,
    version: TWVersion,
) -> TWTestCase | None:
    if test_case_id is None:
        return None
    test_case = await get_test_case(db, test_case_id, current_user)
    assert_same_workbench_scope(version, test_case, "测试用例")
    return test_case


async def _validate_execution_relation(
    db: AsyncSession,
    execution_id: int | None,
    version: TWVersion,
    test_case_id: int | None = None,
) -> None:
    if execution_id is None:
        return
    execution = (await db.execute(select(TWTestExecution).where(
        TWTestExecution.id == execution_id,
        TWTestExecution.is_deleted == False,
    ))).scalar_one_or_none()
    if not execution:
        raise UnifiedException(code=400, message="执行记录不存在")
    execution_case = await get_test_case(db, execution.test_case_id, None)
    assert_same_workbench_scope(version, execution_case, "执行记录")
    if test_case_id is not None and execution.test_case_id != test_case_id:
        raise UnifiedException(code=400, message="执行记录不属于关联测试用例")


async def _validate_planned_version(
    db: AsyncSession,
    planned_version_id: int | None,
    version: TWVersion,
) -> None:
    if planned_version_id is None:
        return
    planned_version = await get_version(db, planned_version_id, None)
    if planned_version.project_id != version.project_id or planned_version.system_id != version.system_id:
        raise UnifiedException(code=400, message="计划版本必须属于当前系统")


async def _validate_bug_relation(
    db: AsyncSession,
    bug_id: int | None,
    version: TWVersion,
) -> None:
    if bug_id is None:
        return
    bug = (await db.execute(select(TWBugRecord).where(
        TWBugRecord.id == bug_id,
        TWBugRecord.is_deleted == False,
    ))).scalar_one_or_none()
    if not bug:
        raise UnifiedException(code=400, message="Bug 不存在")
    assert_same_workbench_scope(version, bug, "Bug")
