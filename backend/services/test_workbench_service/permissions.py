"""测试工作台服务：权限校验、资产查询与出参组装。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions import is_manager, is_super_admin
from core.response import UnifiedException
from models.models import (
    TWProject,
    TWBugRecord,
    TWCompletedRequirement,
    TWMergedRequirement,
    TWRequirement,
    TWSystem,
    TWTestCase,
    TWVersion,
    User,
)

from ._shared import (
    allocate_scoped_case_no_strings,
    normalize_structure,
    structure_is_empty,
    to_dict,
)
from .records import get_active_workbench_record


async def allocate_version_case_numbers(db: AsyncSession, version: TWVersion, count: int) -> list[str]:
    """锁定当前版本后，在该系统、版本作用域内连续分配用例编号。"""
    if count <= 0:
        return []
    await db.execute(select(TWVersion.id).where(TWVersion.id == version.id).with_for_update())
    rows = (await db.execute(
        select(TWTestCase.case_no).where(
            TWTestCase.project_id == version.project_id,
            TWTestCase.system_id == version.system_id,
            TWTestCase.version_id == version.id,
        ).with_for_update()
    )).scalars().all()
    system_name = (await db.execute(select(TWSystem.name).where(TWSystem.id == version.system_id))).scalar_one_or_none()
    return allocate_scoped_case_no_strings({str(item) for item in rows if item}, system_name, version.version_no, count)


def assert_same_workbench_scope(current: Any, related: Any, asset_name: str) -> None:
    """确保可选关联资产仍属于当前项目、系统与版本。"""
    current_version_id = getattr(current, "version_id", current.id)
    if (
        current.project_id != related.project_id
        or current.system_id != related.system_id
        or current_version_id != related.version_id
    ):
        raise UnifiedException(code=400, message=f"关联{asset_name}不属于当前版本")


def execution_result_details(result: str) -> None:
    """执行状态统一收敛为通过、失败、未执行三态。"""
    if result not in {"passed", "failed", "not_executed"}:
        raise UnifiedException(code=400, message="执行结果不合法")


def project_to_dict(project: TWProject) -> dict[str, Any]:
    return to_dict(project)


async def get_owned_project(db: AsyncSession, project_id: int, user: User) -> TWProject:
    project = await get_project(db, project_id, user)
    if not can_manage_workbench_project_settings(user, project):
        raise UnifiedException(code=403, message="权限不足")
    return project


def can_access_workbench_project(user: User | None, project: TWProject | Any) -> bool:
    """工作台项目访问：超管、创建人可访问全部，其他角色仅可访问公开项目。"""
    if not user or not project:
        return False
    return bool(
        is_super_admin(user)
        or getattr(project, "is_public", False)
        or getattr(project, "created_by", None) == user.id
    )


def can_manage_workbench_project_settings(user: User | None, project: TWProject | Any) -> bool:
    """工作台项目本身的编辑、删除仅限创建人和超管。"""
    if not user or not project:
        return False
    return bool(
        is_super_admin(user)
        or getattr(project, "created_by", None) == user.id
    )


def can_manage_project_workbench_record(user: User, project: TWProject, record: Any) -> bool:
    """超管、项目创建人可管理全部；管理员可管理公开项目；普通用户仅管理本人资产。"""
    if is_super_admin(user) or getattr(project, "created_by", None) == user.id:
        return True
    if is_manager(user) and getattr(project, "is_public", True):
        return True
    return bool(
        getattr(project, "is_public", True)
        and getattr(record, "created_by", None) == user.id
    )


def split_manageable_workbench_records(
    user: User, project: TWProject, records: list[Any],
) -> tuple[list[Any], list[Any]]:
    """按当前用户权限拆分批量操作目标与跳过目标。"""
    manageable: list[Any] = []
    skipped: list[Any] = []
    for record in records:
        (manageable if can_manage_project_workbench_record(user, project, record) else skipped).append(record)
    return manageable, skipped


def ensure_manageable_workbench_records(user: User, project: TWProject, records: list[Any]) -> None:
    """批量操作选中记录时执行全量权限预检，避免先改后报错。"""
    _, skipped = split_manageable_workbench_records(user, project, records)
    if skipped:
        raise UnifiedException(code=403, message="权限不足")


def can_operate_bug_workflow(user: User, project: TWProject, bug: TWBugRecord, action: str) -> bool:
    """Bug 流程动作额外允许当前处理人或验证人执行其对应职责。"""
    if can_manage_project_workbench_record(user, project, bug):
        return True
    if action == "resolve":
        return user.id == bug.assignee_id
    if action == "verify":
        return user.id == (bug.verifier_id or bug.created_by)
    return False


async def get_project(db: AsyncSession, project_id: int, user: User | None = None) -> TWProject:
    project = await get_active_workbench_record(
        db,
        TWProject,
        project_id,
        not_found_message="权限不足" if user else "项目不存在",
        not_found_code=403 if user else 400,
    )
    if user and not can_access_workbench_project(user, project):
        raise UnifiedException(code=403, message="权限不足")
    return project


async def ensure_manage_workbench_record(db: AsyncSession, user: User, record: Any) -> None:
    """按项目与创建人校验资产维护权限。"""
    project = await get_project(db, record.project_id, user)
    if not can_manage_project_workbench_record(user, project, record):
        raise UnifiedException(code=403, message="权限不足")


async def get_system(db: AsyncSession, system_id: int, user: User) -> TWSystem:
    system = await get_active_workbench_record(
        db, TWSystem, system_id, not_found_message="系统不存在",
    )
    await get_project(db, system.project_id, user)
    return system


async def get_version(db: AsyncSession, version_id: int, user: User) -> TWVersion:
    version = await get_active_workbench_record(
        db, TWVersion, version_id, not_found_message="版本不存在",
    )
    await get_project(db, version.project_id, user)
    return version


async def get_requirement(db: AsyncSession, requirement_id: int, user: User) -> TWRequirement:
    requirement = await get_active_workbench_record(
        db, TWRequirement, requirement_id, not_found_message="需求不存在",
    )
    await get_project(db, requirement.project_id, user)
    return requirement


async def get_completed_requirement(
    db: AsyncSession,
    completed_requirement_id: int,
    user: User,
) -> TWCompletedRequirement:
    completed = await get_active_workbench_record(
        db,
        TWCompletedRequirement,
        completed_requirement_id,
        not_found_message="补全需求不存在",
    )
    await get_project(db, completed.project_id, user)
    return completed


async def mark_completed_requirements_stale(
    db: AsyncSession,
    source_requirement_id: int,
) -> int:
    """原始需求正文变化时，仅标记其补全需求可能过期，不改变补全需求确认状态。"""
    rows = (await db.execute(
        select(TWCompletedRequirement).where(
            TWCompletedRequirement.source_requirement_id == source_requirement_id,
            TWCompletedRequirement.is_deleted == False,
        )
    )).scalars().all()
    for row in rows:
        row.is_stale = True
    return len(rows)


async def mark_requirement_dependents_source_deleted(db: AsyncSession, source_requirement_id: int) -> None:
    """原始来源删除后，其补全/合并衍生物仍保留，但不能再作为后续测试资产来源。"""
    completed_rows = (await db.execute(select(TWCompletedRequirement).where(
        TWCompletedRequirement.source_requirement_id == source_requirement_id,
        TWCompletedRequirement.is_deleted == False,
    ))).scalars().all()
    for completed in completed_rows:
        completed.is_stale = True
    merged_rows = (await db.execute(select(TWMergedRequirement).where(
        TWMergedRequirement.is_deleted == False,
    ))).scalars().all()
    for merged in merged_rows:
        source_ids = {
            item.get("requirement_id") or item.get("source_id")
            for item in (merged.source_requirement_ids or [])
            if isinstance(item, dict) and (item.get("source_type") or "requirement") == "requirement"
        }
        if source_requirement_id in source_ids:
            merged.is_stale = True


async def get_test_case(db: AsyncSession, test_case_id: int, user: User) -> TWTestCase:
    test_case = await get_active_workbench_record(
        db, TWTestCase, test_case_id, not_found_message="测试用例不存在",
    )
    await get_project(db, test_case.project_id, user)
    return test_case


async def get_merged_requirement(db: AsyncSession, merged_requirement_id: int, user: User | None = None) -> TWMergedRequirement:
    merged = await get_active_workbench_record(
        db,
        TWMergedRequirement,
        merged_requirement_id,
        not_found_message="合并需求不存在",
    )
    await get_project(db, merged.project_id, user)
    return merged


def merged_requirement_to_dict(merged: TWMergedRequirement) -> dict[str, Any]:
    """合并需求出参：结构化 JSON 归一化为固定 5 键，并派生 is_structured 供前端直接使用。"""
    data = to_dict(merged)
    data["structure_json"] = normalize_structure(merged.structure_json)
    # 是否已生成结构化需求：基于 structure_json 是否非空派生，前端不再自行判空。
    data["is_structured"] = not structure_is_empty(merged.structure_json)
    return data


def assign_requirement_no(requirement, prefix: str = "REQ") -> str | None:
    """需求保存落库时分配稳定唯一编号；已有编号则不变（幂等）。

    基于自增主键生成（REQ-000123 / MREQ-000123），天然稳定唯一，无需额外序列表。
    调用前需保证 requirement.id 已生成（新建后已 flush）。
    """
    if getattr(requirement, "req_no", None):
        return requirement.req_no
    if not getattr(requirement, "id", None):
        return None
    requirement.req_no = f"{prefix}-{requirement.id:06d}"
    return requirement.req_no


async def mark_merged_requirements_stale(
    db: AsyncSession, requirement_id: int, source_type: str = "requirement",
) -> list[str]:
    """来源需求被就地编辑后，把包含它的合并需求打「可能过期」软标记，返回被标记的合并需求标题。"""
    # 来源快照经历过字段升级，兼容 requirement_id 和 source_id 两种记录；
    # 这里宁可读取当前项目中的合并需求后在内存精确匹配，避免 JSON contains 因骨架不同漏标。
    rows = (await db.execute(select(TWMergedRequirement).where(
        TWMergedRequirement.is_deleted == False,
    ))).scalars().all()
    titles: list[str] = []
    for merged in rows:
        source_ids = {
            item.get("requirement_id") or item.get("source_id")
            for item in (merged.source_requirement_ids or [])
            if isinstance(item, dict) and (not item.get("source_type") or item.get("source_type") == source_type)
        }
        if requirement_id in source_ids and not merged.is_stale:
            merged.is_stale = True
            titles.append(merged.title)
    return titles


async def merged_requirement_titles_for_source(
    db: AsyncSession, requirement_id: int, source_type: str = "requirement",
) -> list[str]:
    """返回把该来源需求合并进去的合并需求标题（用于需求追溯与编辑前提示）。"""
    rows = (await db.execute(
        select(TWMergedRequirement).where(TWMergedRequirement.is_deleted == False)
    )).scalars().all()
    titles: list[str] = []
    for merged in rows:
        source_ids = {
            item.get("requirement_id") or item.get("source_id")
            for item in (merged.source_requirement_ids or [])
            if isinstance(item, dict) and (item.get("source_type") or "requirement") == source_type
        }
        if requirement_id in source_ids:
            titles.append(merged.title)
    return titles


async def paged(query, count_query, db: AsyncSession, page: int, page_size: int):
    total = (await db.execute(count_query)).scalar() or 0
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [to_dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}
