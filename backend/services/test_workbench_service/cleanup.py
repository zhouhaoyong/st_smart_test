"""测试工作台服务：项目/系统/版本删除校验与业务数据清理。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from models.models import (
    TWBugRecord,
    TWBugTransition,
    TWCompletedRequirement,
    TWLegacyItem,
    TWMergedRequirement,
    TWProject,
    TWRequirement,
    TWSystem,
    TWTestCase,
    TWTestExecution,
    TWVersion,
)
from services.test_workbench_audit import soft_delete_workbench_record


PROJECT_BUSINESS_CLEANUP_TYPES = (
    "system", "version", "requirement", "test_case", "bug", "legacy_item",
)
PROJECT_BUSINESS_CHILD_CLEANUP_TYPES = (
    "requirement", "test_case", "bug", "legacy_item",
)
PROJECT_BUSINESS_CLEANUP_SUMMARY_KEYS = {
    "system": ("system_count",),
    "version": ("version_count",),
    "requirement": ("requirement_count",),
    "test_case": ("test_case_count", "test_execution_count"),
    "bug": ("bug_count", "bug_transition_count"),
    "legacy_item": ("legacy_item_count",),
}


def project_business_cleanup_parent_ids(
    model,
    project_id: int,
    system_ids: list[int] | None = None,
):
    """返回清理关联记录使用的未删除父数据 ID 范围。"""
    conditions = [
        model.project_id == project_id,
        model.is_deleted.is_(False),
    ]
    if system_ids:
        conditions.append(model.system_id.in_(system_ids))
    return select(model.id).where(*conditions)


async def ensure_project_deletable(db: AsyncSession, project_id: int) -> None:
    asset_models = (TWSystem, TWVersion, TWRequirement, TWCompletedRequirement, TWMergedRequirement, TWTestCase, TWBugRecord, TWLegacyItem)
    for model in asset_models:
        has_asset = (await db.execute(select(func.count()).select_from(model).where(
            model.project_id == project_id,
            model.is_deleted == False,
        ))).scalar() or 0
        if has_asset:
            raise UnifiedException(code=400, message="项目下已有业务数据，无法删除")


async def _project_records(db: AsyncSession, model, project_id: int) -> list:
    result = await db.execute(select(model).where(
        model.project_id == project_id,
    ))
    return list(result.scalars().all())


async def _active_related_records(db: AsyncSession, model, relation_column, related_ids: list[int]) -> list:
    if not related_ids:
        return []
    result = await db.execute(select(model).where(
        relation_column.in_(related_ids),
        model.is_deleted == False,
    ))
    return list(result.scalars().all())


async def soft_delete_workbench_project_data(
    db: AsyncSession,
    project: TWProject,
    current_user_id: int,
    deleted_at: datetime,
) -> dict[str, int]:
    """软删除工作台项目及其全部关联数据。"""
    project_id = project.id
    parent_models = (
        TWSystem,
        TWVersion,
        TWRequirement,
        TWCompletedRequirement,
        TWMergedRequirement,
        TWTestCase,
        TWBugRecord,
        TWLegacyItem,
    )
    all_records_by_model = {
        model: await _project_records(db, model, project_id)
        for model in parent_models
    }
    records_by_model = {
        model: [record for record in records if not record.is_deleted]
        for model, records in all_records_by_model.items()
    }
    test_case_ids = [record.id for record in all_records_by_model[TWTestCase]]
    bug_ids = [record.id for record in all_records_by_model[TWBugRecord]]
    test_executions = await _active_related_records(
        db, TWTestExecution, TWTestExecution.test_case_id, test_case_ids,
    )
    bug_transitions = await _active_related_records(
        db, TWBugTransition, TWBugTransition.bug_id, bug_ids,
    )

    # 先处理子记录，再处理项目资产和项目本身，保证关联数据不会残留。
    for records in (
        test_executions,
        bug_transitions,
        *records_by_model.values(),
        [project],
    ):
        for record in records:
            soft_delete_workbench_record(record, current_user_id, deleted_at)

    return {
        "system_count": len(records_by_model[TWSystem]),
        "version_count": len(records_by_model[TWVersion]),
        "requirement_count": len(records_by_model[TWRequirement]),
        "completed_requirement_count": len(records_by_model[TWCompletedRequirement]),
        "merged_requirement_count": len(records_by_model[TWMergedRequirement]),
        "test_case_count": len(records_by_model[TWTestCase]),
        "bug_count": len(records_by_model[TWBugRecord]),
        "legacy_item_count": len(records_by_model[TWLegacyItem]),
        "test_execution_count": len(test_executions),
        "bug_transition_count": len(bug_transitions),
    }


async def ensure_system_deletable(db: AsyncSession, system_id: int) -> None:
    has_version = (await db.execute(select(func.count()).select_from(TWVersion).where(
        TWVersion.system_id == system_id,
        TWVersion.is_deleted == False,
    ))).scalar() or 0
    if has_version:
        raise UnifiedException(code=400, message="系统下已有版本数据，无法删除")


async def ensure_version_deletable(db: AsyncSession, version_id: int) -> None:
    asset_models = (TWRequirement, TWCompletedRequirement, TWMergedRequirement, TWTestCase, TWBugRecord, TWLegacyItem)
    for model in asset_models:
        has_asset = (await db.execute(select(func.count()).select_from(model).where(
            model.version_id == version_id,
            model.is_deleted == False,
        ))).scalar() or 0
        if has_asset:
            raise UnifiedException(code=400, message="版本下已有测试资产，无法删除")


def validate_project_business_cleanup_types(asset_types: list[str]) -> set[str]:
    """校验项目数据清理的上层范围不会遗留有效的下属业务数据。"""
    selected_types = set(asset_types)
    if not selected_types or not selected_types.issubset(PROJECT_BUSINESS_CLEANUP_TYPES):
        raise UnifiedException(code=400, message="清理数据类型不合法")
    if "version" in selected_types and not set(PROJECT_BUSINESS_CHILD_CLEANUP_TYPES).issubset(selected_types):
        raise UnifiedException(code=400, message="清理版本前需同时选择其下全部业务数据")
    if "system" in selected_types and not {"version", *PROJECT_BUSINESS_CHILD_CLEANUP_TYPES}.issubset(selected_types):
        raise UnifiedException(code=400, message="清理系统前需同时选择版本及全部业务数据")
    return selected_types


async def ensure_project_business_cleanup_systems(
    db: AsyncSession, project_id: int, system_ids: list[int],
) -> None:
    existing_ids = set((await db.execute(select(TWSystem.id).where(
        TWSystem.project_id == project_id,
        TWSystem.id.in_(system_ids),
        TWSystem.is_deleted == False,
    ))).scalars().all())
    if existing_ids != set(system_ids):
        raise UnifiedException(code=400, message="所选系统不存在或不属于当前项目")


async def get_project_business_cleanup_summary(
    db: AsyncSession, project_id: int, system_ids: list[int] | None = None,
) -> dict[str, int]:
    """统计所选系统下的业务数据清理范围。"""

    selected_system_ids = list(dict.fromkeys(system_ids or []))

    async def _count(model, *conditions) -> int:
        return (await db.execute(
            select(func.count()).select_from(model).where(model.is_deleted == False, *conditions)
        )).scalar() or 0

    def _asset_scope(model) -> list:
        conditions = [model.project_id == project_id]
        if selected_system_ids:
            conditions.append(model.system_id.in_(selected_system_ids))
        return conditions

    system_scope = [TWSystem.project_id == project_id]
    version_scope = [TWVersion.project_id == project_id]
    if selected_system_ids:
        system_scope.append(TWSystem.id.in_(selected_system_ids))
        version_scope.append(TWVersion.system_id.in_(selected_system_ids))

    test_case_ids = project_business_cleanup_parent_ids(TWTestCase, project_id, selected_system_ids)
    bug_ids = project_business_cleanup_parent_ids(TWBugRecord, project_id, selected_system_ids)
    requirement_count = sum([
        await _count(TWRequirement, *_asset_scope(TWRequirement)),
        await _count(TWCompletedRequirement, *_asset_scope(TWCompletedRequirement)),
        await _count(TWMergedRequirement, *_asset_scope(TWMergedRequirement)),
    ])
    return {
        "legacy_item_count": await _count(TWLegacyItem, *_asset_scope(TWLegacyItem)),
        "bug_count": await _count(TWBugRecord, *_asset_scope(TWBugRecord)),
        "bug_transition_count": await _count(TWBugTransition, TWBugTransition.bug_id.in_(bug_ids)),
        "test_case_count": await _count(TWTestCase, *_asset_scope(TWTestCase)),
        "test_execution_count": await _count(TWTestExecution, TWTestExecution.test_case_id.in_(test_case_ids)),
        "requirement_count": requirement_count,
        "version_count": await _count(TWVersion, *version_scope),
        "system_count": await _count(TWSystem, *system_scope),
    }


def selected_project_business_cleanup_summary(summary: dict[str, int], asset_types: set[str]) -> dict[str, int]:
    result = {key: 0 for keys in PROJECT_BUSINESS_CLEANUP_SUMMARY_KEYS.values() for key in keys}
    for asset_type in asset_types:
        for key in PROJECT_BUSINESS_CLEANUP_SUMMARY_KEYS[asset_type]:
            result[key] = summary[key]
    return result


async def soft_delete_project_business_data(
    db: AsyncSession,
    project_id: int,
    current_user_id: int,
    deleted_at: datetime,
    system_ids: list[int],
    asset_types: list[str],
) -> dict[str, int]:
    """软删除所选系统下的业务数据，并一并清理从属的执行与流转记录。"""
    selected_types = validate_project_business_cleanup_types(asset_types)
    summary = await get_project_business_cleanup_summary(db, project_id, system_ids)

    def _asset_scope(model) -> list:
        return [model.project_id == project_id, model.system_id.in_(system_ids)]

    test_case_ids = project_business_cleanup_parent_ids(TWTestCase, project_id, system_ids)
    bug_ids = project_business_cleanup_parent_ids(TWBugRecord, project_id, system_ids)
    cleanup_scopes = []
    if "legacy_item" in selected_types:
        cleanup_scopes.append((TWLegacyItem, _asset_scope(TWLegacyItem)))
    if "bug" in selected_types:
        cleanup_scopes.extend(((TWBugTransition, [TWBugTransition.bug_id.in_(bug_ids)]), (TWBugRecord, _asset_scope(TWBugRecord))))
    if "test_case" in selected_types:
        cleanup_scopes.extend(((TWTestExecution, [TWTestExecution.test_case_id.in_(test_case_ids)]), (TWTestCase, _asset_scope(TWTestCase))))
    if "requirement" in selected_types:
        cleanup_scopes.extend(((TWMergedRequirement, _asset_scope(TWMergedRequirement)), (TWCompletedRequirement, _asset_scope(TWCompletedRequirement)), (TWRequirement, _asset_scope(TWRequirement))))
    if "version" in selected_types:
        cleanup_scopes.append((TWVersion, [TWVersion.project_id == project_id, TWVersion.system_id.in_(system_ids)]))
    if "system" in selected_types:
        cleanup_scopes.append((TWSystem, [TWSystem.project_id == project_id, TWSystem.id.in_(system_ids)]))
    for model, condition in cleanup_scopes:
        records = (await db.execute(select(model).where(model.is_deleted == False, *condition))).scalars().all()
        for record in records:
            soft_delete_workbench_record(record, current_user_id, deleted_at)
    return selected_project_business_cleanup_summary(summary, selected_types)
