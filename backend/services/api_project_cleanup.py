"""API 测试项目数据清理服务。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from models.models import (
    Environment,
    ExecutionItem,
    ExecutionSet,
    Interface,
    InterfaceCollection,
    ParameterItem,
    ParameterSet,
    Report,
    ReportDetail,
    ReportSendLog,
    SchedulePolicyBinding,
    TestCase,
)


API_PROJECT_CLEANUP_TYPES = (
    "environment",
    "interface",
    "test_case",
    "parameter_set",
    "execution_set",
    "report",
)
API_PROJECT_CLEANUP_SUMMARY_KEYS = {
    "environment": ("environment_count",),
    "interface": (
        "interface_count",
        "interface_collection_count",
        "interface_case_count",
        "interface_execution_item_count",
    ),
    "test_case": ("test_case_count", "test_case_execution_item_count"),
    "parameter_set": ("parameter_set_count", "parameter_item_count"),
    "execution_set": (
        "execution_set_count",
        "execution_set_item_count",
        "execution_set_report_reference_count",
    ),
    "report": ("report_count", "report_detail_count", "report_send_log_count"),
}


def project_cleanup_parent_ids(model, project_id: int):
    """返回当前项目下可清理的、未删除父数据 ID。"""
    return select(model.id).where(
        model.project_id == project_id,
        model.is_deleted.is_(False),
    )


def validate_api_project_cleanup_types(asset_types: list[str]) -> set[str]:
    """校验 API 测试项目清理模块。"""
    selected_types = set(asset_types)
    if not selected_types or not selected_types.issubset(API_PROJECT_CLEANUP_TYPES):
        raise UnifiedException(code=400, message="清理数据类型不合法")
    return selected_types


def selected_api_project_cleanup_summary(
    summary: dict[str, int], asset_types: set[str],
) -> dict[str, int]:
    """仅返回用户选中的模块及其级联数据统计。"""
    result = {key: 0 for keys in API_PROJECT_CLEANUP_SUMMARY_KEYS.values() for key in keys}
    for asset_type in asset_types:
        for key in API_PROJECT_CLEANUP_SUMMARY_KEYS[asset_type]:
            result[key] = summary.get(key, 0)
    return result


async def _count(db: AsyncSession, statement) -> int:
    return (await db.execute(statement)).scalar() or 0


async def get_api_project_business_cleanup_summary(
    db: AsyncSession, project_id: int,
) -> dict[str, int]:
    """统计 API 测试项目下六类数据及其内部关联数据。"""
    active_environment = [Environment.project_id == project_id, Environment.is_deleted == False]
    active_collection = [InterfaceCollection.project_id == project_id, InterfaceCollection.is_deleted == False]
    active_interface = [Interface.is_deleted == False]
    active_test_case = [TestCase.project_id == project_id, TestCase.is_deleted == False]
    active_parameter_set = [ParameterSet.project_id == project_id, ParameterSet.is_deleted == False]
    active_execution_set = [ExecutionSet.project_id == project_id, ExecutionSet.is_deleted == False]
    active_report = [Report.project_id == project_id, Report.is_deleted == False]

    interface_ids = select(Interface.id).join(
        InterfaceCollection, Interface.collection_id == InterfaceCollection.id,
    ).where(*active_collection, *active_interface)
    test_case_ids = select(TestCase.id).where(*active_test_case)
    execution_set_ids = select(ExecutionSet.id).where(*active_execution_set)
    report_ids = select(Report.id).where(*active_report)

    return {
        "environment_count": await _count(
            db, select(func.count()).select_from(Environment).where(*active_environment),
        ),
        "interface_collection_count": await _count(
            db, select(func.count()).select_from(InterfaceCollection).where(*active_collection),
        ),
        "interface_count": await _count(
            db, select(func.count()).select_from(Interface).join(
                InterfaceCollection, Interface.collection_id == InterfaceCollection.id,
            ).where(*active_collection, *active_interface),
        ),
        "interface_case_count": await _count(
            db, select(func.count()).select_from(TestCase).join(
                Interface, TestCase.interface_id == Interface.id,
            ).join(
                InterfaceCollection, Interface.collection_id == InterfaceCollection.id,
            ).where(*active_collection, *active_interface, *active_test_case),
        ),
        "interface_execution_item_count": await _count(
            db, select(func.count()).select_from(ExecutionItem).join(
                TestCase, ExecutionItem.test_case_id == TestCase.id,
            ).join(ExecutionSet, ExecutionItem.execution_set_id == ExecutionSet.id).where(
                ExecutionItem.is_deleted == False,
                ExecutionSet.project_id == project_id,
                ExecutionSet.is_deleted == False,
                TestCase.interface_id.in_(interface_ids),
                TestCase.is_deleted == False,
            ),
        ),
        "test_case_count": await _count(
            db, select(func.count()).select_from(TestCase).where(*active_test_case),
        ),
        "test_case_execution_item_count": await _count(
            db, select(func.count(func.distinct(ExecutionItem.test_case_id))).select_from(ExecutionItem).join(
                ExecutionSet, ExecutionItem.execution_set_id == ExecutionSet.id,
            ).where(
                ExecutionItem.is_deleted == False,
                ExecutionSet.project_id == project_id,
                ExecutionSet.is_deleted == False,
                ExecutionItem.test_case_id.in_(test_case_ids),
            ),
        ),
        "parameter_set_count": await _count(
            db, select(func.count()).select_from(ParameterSet).where(*active_parameter_set),
        ),
        "parameter_item_count": await _count(
            db, select(func.count()).select_from(ParameterItem).where(
                ParameterItem.is_deleted == False,
                ParameterItem.parameter_set_id.in_(
                    select(ParameterSet.id).where(*active_parameter_set),
                ),
            ),
        ),
        "execution_set_count": await _count(
            db, select(func.count()).select_from(ExecutionSet).where(*active_execution_set),
        ),
        "execution_set_item_count": await _count(
            db, select(func.count()).select_from(ExecutionItem).where(
                ExecutionItem.is_deleted == False,
                ExecutionItem.execution_set_id.in_(execution_set_ids),
            ),
        ),
        "execution_set_report_reference_count": await _count(
            db, select(func.count()).select_from(Report).where(
                Report.is_deleted == False,
                Report.execution_set_id.in_(execution_set_ids),
            ),
        ),
        "report_count": await _count(
            db, select(func.count()).select_from(Report).where(*active_report),
        ),
        "report_detail_count": await _count(
            db, select(func.count()).select_from(ReportDetail).where(
                ReportDetail.is_deleted == False,
                ReportDetail.report_id.in_(report_ids),
            ),
        ),
        "report_send_log_count": await _count(
            db, select(func.count()).select_from(ReportSendLog).where(
                ReportSendLog.is_deleted == False,
                ReportSendLog.report_id.in_(report_ids),
            ),
        ),
    }


async def _active_records(db: AsyncSession, model, *conditions) -> list:
    result = await db.execute(select(model).where(model.is_deleted == False, *conditions))
    return list(result.scalars().all())


async def _active_project_execution_items(
    db: AsyncSession,
    project_id: int,
    *,
    case_ids: list[int] | None = None,
    execution_set_ids: list[int] | None = None,
) -> list[ExecutionItem]:
    query = select(ExecutionItem).join(
        ExecutionSet, ExecutionItem.execution_set_id == ExecutionSet.id,
    ).where(
        ExecutionItem.is_deleted == False,
        ExecutionSet.project_id == project_id,
        ExecutionSet.is_deleted == False,
    )
    if case_ids:
        query = query.where(ExecutionItem.test_case_id.in_(case_ids))
    if execution_set_ids:
        query = query.where(ExecutionItem.execution_set_id.in_(execution_set_ids))
    result = await db.execute(query)
    return list(result.scalars().all())


def _soft_delete_records(records: list, current_user_id: int, deleted_at: datetime) -> None:
    for record in records:
        record.is_deleted = True
        record.deleted_at = deleted_at
        if hasattr(record, "updated_by"):
            record.updated_by = current_user_id


async def soft_delete_api_project_business_data(
    db: AsyncSession,
    project_id: int,
    current_user_id: int,
    deleted_at: datetime,
    asset_types: list[str],
) -> dict[str, int]:
    """软删除选中的 API 测试项目数据，并清理内部关联。"""
    selected_types = validate_api_project_cleanup_types(asset_types)
    summary = await get_api_project_business_cleanup_summary(db, project_id)

    if "environment" in selected_types:
        environments = await _active_records(db, Environment, Environment.project_id == project_id)
        environment_ids = [item.id for item in environments]
        if environment_ids:
            execution_sets = await _active_records(
                db, ExecutionSet, ExecutionSet.project_id == project_id,
                ExecutionSet.environment_id.in_(environment_ids),
            )
            for execution_set in execution_sets:
                execution_set.environment_id = None
        _soft_delete_records(environments, current_user_id, deleted_at)

    if "interface" in selected_types:
        collections = await _active_records(db, InterfaceCollection, InterfaceCollection.project_id == project_id)
        collection_ids = [item.id for item in collections]
        interfaces = []
        if collection_ids:
            result = await db.execute(select(Interface).where(
                Interface.collection_id.in_(collection_ids),
                Interface.is_deleted == False,
            ))
            interfaces = list(result.scalars().all())
        interface_ids = [item.id for item in interfaces]
        cases = []
        if interface_ids:
            cases = await _active_records(
                db, TestCase, TestCase.project_id == project_id,
                TestCase.interface_id.in_(interface_ids),
            )
        case_ids = [item.id for item in cases]
        if case_ids:
            execution_items = await _active_project_execution_items(db, project_id, case_ids=case_ids)
            _soft_delete_records(execution_items, current_user_id, deleted_at)
        _soft_delete_records(cases, current_user_id, deleted_at)
        _soft_delete_records(interfaces, current_user_id, deleted_at)
        _soft_delete_records(collections, current_user_id, deleted_at)

    if "test_case" in selected_types:
        cases = await _active_records(db, TestCase, TestCase.project_id == project_id)
        case_ids = [item.id for item in cases]
        if case_ids:
            execution_items = await _active_project_execution_items(db, project_id, case_ids=case_ids)
            _soft_delete_records(execution_items, current_user_id, deleted_at)
        _soft_delete_records(cases, current_user_id, deleted_at)

    if "parameter_set" in selected_types:
        parameter_sets = await _active_records(db, ParameterSet, ParameterSet.project_id == project_id)
        parameter_set_ids = [item.id for item in parameter_sets]
        if parameter_set_ids:
            items = await _active_records(db, ParameterItem, ParameterItem.parameter_set_id.in_(parameter_set_ids))
            execution_sets = await _active_records(
                db, ExecutionSet, ExecutionSet.project_id == project_id,
                ExecutionSet.parameter_set_id.in_(parameter_set_ids),
            )
            for execution_set in execution_sets:
                execution_set.parameter_set_id = None
            _soft_delete_records(items, current_user_id, deleted_at)
        _soft_delete_records(parameter_sets, current_user_id, deleted_at)

    if "execution_set" in selected_types:
        execution_sets = await _active_records(db, ExecutionSet, ExecutionSet.project_id == project_id)
        execution_set_ids = [item.id for item in execution_sets]
        if execution_set_ids:
            execution_items = await _active_project_execution_items(
                db, project_id, execution_set_ids=execution_set_ids,
            )
            reports = await _active_records(
                db, Report, Report.project_id == project_id,
                Report.execution_set_id.in_(execution_set_ids),
            )
            bindings = await _active_records(
                db, SchedulePolicyBinding,
                SchedulePolicyBinding.module == "api_test",
                SchedulePolicyBinding.target_type == "execution_set",
                SchedulePolicyBinding.target_id.in_(execution_set_ids),
            )
            for report in reports:
                report.execution_set_id = None
            for binding in bindings:
                binding.is_enabled = False
            _soft_delete_records(execution_items, current_user_id, deleted_at)
            _soft_delete_records(bindings, current_user_id, deleted_at)
        _soft_delete_records(execution_sets, current_user_id, deleted_at)

    if "report" in selected_types:
        reports = await _active_records(db, Report, Report.project_id == project_id)
        report_ids = [item.id for item in reports]
        if report_ids:
            details = await _active_records(db, ReportDetail, ReportDetail.report_id.in_(report_ids))
            send_logs = await _active_records(db, ReportSendLog, ReportSendLog.report_id.in_(report_ids))
            _soft_delete_records(details, current_user_id, deleted_at)
            _soft_delete_records(send_logs, current_user_id, deleted_at)
        _soft_delete_records(reports, current_user_id, deleted_at)

    return selected_api_project_cleanup_summary(summary, selected_types)
