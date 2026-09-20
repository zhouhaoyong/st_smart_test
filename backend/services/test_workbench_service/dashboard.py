"""测试工作台服务：看板统计、筛选项与资产明细分页查询。"""
from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from models.models import (
    TWBugRecord,
    TWBugTransition,
    TWCompletedRequirement,
    TWLegacyItem,
    TWMergedRequirement,
    TWRequirement,
    TWSystem,
    TWTestCase,
    TWVersion,
    User,
)

from ._shared import normalize_structure, structure_is_empty, to_dict


async def get_project_dashboard_stats(
    db: AsyncSession,
    project_id: int,
    system_id: int | None = None,
    version_id: int | None = None,
    system_ids: list[int] | None = None,
    version_ids: list[int] | None = None,
    current_user_id: int | None = None,
) -> dict[str, Any]:
    """统计工作台资产数量及测试闭环质量指标。

    按当前作用域聚合：默认项目级；传入 system_id / version_id 时聚焦该系统 / 版本（见 PRD 4.12）。
    """

    def _scope(model) -> list:
        """为归属四级的资产追加系统 / 版本作用域过滤。"""
        conditions = []
        if system_ids:
            conditions.append(model.system_id.in_(system_ids))
        elif system_id:
            conditions.append(model.system_id == system_id)
        if version_ids:
            conditions.append(model.version_id.in_(version_ids))
        elif version_id:
            conditions.append(model.version_id == version_id)
        return conditions

    version_scope = []
    if system_ids:
        version_scope.append(TWVersion.system_id.in_(system_ids))
    elif system_id:
        version_scope.append(TWVersion.system_id == system_id)
    if version_ids:
        version_scope.append(TWVersion.id.in_(version_ids))
    elif version_id:
        version_scope.append(TWVersion.id == version_id)

    system_scope = []
    if system_ids:
        system_scope.append(TWSystem.id.in_(system_ids))
    elif system_id:
        system_scope.append(TWSystem.id == system_id)
    elif version_ids:
        system_scope.append(TWSystem.id.in_(select(TWVersion.system_id).where(
            TWVersion.id.in_(version_ids),
            TWVersion.is_deleted == False,
        )))
    elif version_id:
        system_scope.append(TWSystem.id.in_(select(TWVersion.system_id).where(
            TWVersion.id == version_id,
            TWVersion.is_deleted == False,
        )))

    stats = {
        "system_count": (await db.execute(
            select(func.count()).select_from(TWSystem).where(
                TWSystem.project_id == project_id,
                TWSystem.is_deleted == False,
                *system_scope,
            )
        )).scalar() or 0,
        "version_count": (await db.execute(
            select(func.count()).select_from(TWVersion)
            .join(TWSystem, TWSystem.id == TWVersion.system_id)
            .where(
                TWVersion.project_id == project_id,
                TWVersion.is_deleted == False,
                TWSystem.is_deleted == False,
                *version_scope,
            )
        )).scalar() or 0,
    }
    async def _count(model, *extra) -> int:
        return (await db.execute(
            select(func.count()).select_from(model)
            .join(TWSystem, TWSystem.id == model.system_id)
            .join(TWVersion, TWVersion.id == model.version_id)
            .where(
                model.project_id == project_id,
                model.is_deleted == False,
                TWSystem.is_deleted == False,
                TWVersion.is_deleted == False,
                *_scope(model),
                *extra,
            )
        )).scalar() or 0

    # PRD 4.12：本期看板只做数量类指标，不做任何比率指标。
    stats["requirement_count"] = await _count(TWRequirement)
    stats["merged_requirement_count"] = await _count(TWMergedRequirement)
    stats["test_case_count"] = await _count(TWTestCase)
    stats["bug_count"] = await _count(TWBugRecord)
    stats["legacy_item_count"] = await _count(TWLegacyItem)
    # 未关闭 Bug 数：非「已验证关闭」状态。
    stats["open_bug_count"] = await _count(TWBugRecord, TWBugRecord.status.notin_(["closed", "legacy"]))
    # 「我的待办」按项目级统计：待我处理 + 待我验证，不叠加系统/版本作用域。
    if current_user_id:
        my_pending_bug_count = (await db.execute(
            select(func.count()).select_from(TWBugRecord).where(
                TWBugRecord.project_id == project_id,
                TWBugRecord.is_deleted == False,
                TWBugRecord.status == "pending",
                TWBugRecord.assignee_id == current_user_id,
            )
        )).scalar() or 0
        my_verification_bug_count = (await db.execute(
            select(func.count()).select_from(TWBugRecord).where(
                TWBugRecord.project_id == project_id,
                TWBugRecord.is_deleted == False,
                TWBugRecord.status == "resolved",
                or_(
                    TWBugRecord.verifier_id == current_user_id,
                    and_(TWBugRecord.verifier_id.is_(None), TWBugRecord.created_by == current_user_id),
                ),
            )
        )).scalar() or 0
        stats["my_pending_bug_count"] = my_pending_bug_count
        stats["my_verification_bug_count"] = my_verification_bug_count
        stats["my_open_bug_count"] = my_pending_bug_count + my_verification_bug_count
    else:
        stats["my_pending_bug_count"] = 0
        stats["my_verification_bug_count"] = 0
        stats["my_open_bug_count"] = 0
    # 待处理遗留项数：状态为「待处理」。
    stats["pending_legacy_count"] = await _count(TWLegacyItem, TWLegacyItem.status == "pending")
    return stats


async def get_project_dashboard_filters(db: AsyncSession, project_id: int) -> dict[str, list[dict[str, Any]]]:
    """返回项目级资产明细弹窗可用的系统和版本筛选项。"""
    systems = (await db.execute(
        select(TWSystem).where(
            TWSystem.project_id == project_id,
            TWSystem.is_deleted == False,
        ).order_by(TWSystem.name, TWSystem.id)
    )).scalars().all()
    version_rows = (await db.execute(
        select(TWVersion, TWSystem.name.label("system_name"))
        .join(TWSystem, TWSystem.id == TWVersion.system_id)
        .where(
            TWVersion.project_id == project_id,
            TWVersion.is_deleted == False,
            TWSystem.is_deleted == False,
        ).order_by(TWSystem.name, TWVersion.id.desc())
    )).all()
    versions = []
    for version, system_name in version_rows:
        item = to_dict(version)
        item["system_name"] = system_name
        versions.append(item)
    return {"systems": [to_dict(item) for item in systems], "versions": versions}


def _append_created_at_filters(conditions: list[Any], column: Any, created_from: str | None, created_to: str | None) -> None:
    try:
        if created_from:
            start_date = datetime.strptime(created_from, "%Y-%m-%d").date()
            conditions.append(column >= datetime.combine(start_date, time(0, 0, 0)))
        if created_to:
            end_date = datetime.strptime(created_to, "%Y-%m-%d").date()
            conditions.append(column <= datetime.combine(end_date, time(23, 59, 59)))
    except ValueError:
        raise UnifiedException(code=400, message="创建日期格式应为 YYYY-MM-DD")


def append_test_case_list_filters(
    conditions: list[Any],
    *,
    status: str | None = None,
    confirm_status: str | None = None,
    case_no: str | None = None,
    title: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    case_type: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> None:
    """追加与用例列表一致的筛选条件，供列表与“全部删除当前列表”共用。"""
    if status:
        if status == "not_executed":
            # 历史“阻塞/未测试”记录在列表中统一归为“未执行”，新写入仅允许三态。
            conditions.append(TWTestCase.execution_status.in_(("not_executed", "blocked", "not_tested")))
        else:
            conditions.append(TWTestCase.execution_status == status)
    if confirm_status:
        conditions.append(TWTestCase.confirm_status == confirm_status)
    if case_no:
        conditions.append(TWTestCase.case_no.like(f"%{case_no}%"))
    if title:
        conditions.append(TWTestCase.title.like(f"%{title}%"))
    if priority:
        conditions.append(TWTestCase.priority == priority)
    if case_type:
        conditions.append(TWTestCase.case_type == case_type)
    if source == "manual":
        conditions.append(or_(TWTestCase.source_type.is_(None), TWTestCase.source_type != "ai_generated"))
    elif source == "ai_requirement":
        conditions.append(and_(
            TWTestCase.source_type == "ai_generated",
            or_(TWTestCase.source_ref.is_(None), TWTestCase.source_ref.like("requirement:%")),
        ))
    elif source == "ai_completed":
        conditions.append(and_(
            TWTestCase.source_type == "ai_generated",
            TWTestCase.source_ref.like("completed_requirement:%"),
        ))
    elif source == "ai_merged":
        conditions.append(and_(
            TWTestCase.source_type == "ai_generated",
            TWTestCase.source_ref.like("merged_requirement:%"),
        ))
    _append_created_at_filters(conditions, TWTestCase.created_at, created_from, created_to)


async def list_project_dashboard_assets(
    db: AsyncSession,
    project_id: int,
    asset_type: str,
    system_id: int | None = None,
    version_id: int | None = None,
    system_ids: list[int] | None = None,
    version_ids: list[int] | None = None,
    status: str | None = None,
    confirm_status: str | None = None,
    name: str | None = None,
    version_no: str | None = None,
    case_no: str | None = None,
    title: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    case_type: str | None = None,
    item_type: str | None = None,
    current_stage: str | None = None,
    severity: str | None = None,
    merge_status: str | None = None,
    assignee_id: int | None = None,
    workflow_view: str | None = None,
    current_user_id: int | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """分页查询项目下某一种测试资产，并补齐系统和版本展示字段。"""
    if asset_type == "scope":
        system_conditions = [TWSystem.project_id == project_id, TWSystem.is_deleted == False]
        if name:
            system_conditions.append(TWSystem.name.like(f"%{name}%"))

        version_conditions = [
            TWVersion.project_id == project_id,
            TWVersion.is_deleted == False,
        ]
        if version_no:
            version_conditions.append(TWVersion.version_no.like(f"%{version_no}%"))
        if current_stage:
            version_conditions.append(TWVersion.current_stage.like(f"%{current_stage}%"))
        if version_no or current_stage:
            system_conditions.append(TWSystem.id.in_(select(TWVersion.system_id).where(*version_conditions)))

        total = (await db.execute(
            select(func.count()).select_from(TWSystem).where(*system_conditions)
        )).scalar() or 0
        systems = (await db.execute(
            select(TWSystem)
            .where(*system_conditions)
            .order_by(TWSystem.created_at.desc(), TWSystem.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()
        system_ids_on_page = [item.id for item in systems]

        versions_by_system: dict[int, list[dict[str, Any]]] = {}
        version_counts: dict[int, int] = {}
        if system_ids_on_page:
            count_rows = (await db.execute(
                select(TWVersion.system_id, func.count())
                .where(
                    TWVersion.project_id == project_id,
                    TWVersion.system_id.in_(system_ids_on_page),
                    TWVersion.is_deleted == False,
                )
                .group_by(TWVersion.system_id)
            )).all()
            version_counts = {system_id: count for system_id, count in count_rows}
            version_rows = (await db.execute(
                select(TWVersion)
                .where(*version_conditions, TWVersion.system_id.in_(system_ids_on_page))
                .order_by(TWVersion.system_id, TWVersion.created_at.desc(), TWVersion.id.desc())
            )).scalars().all()
            for version in version_rows:
                versions_by_system.setdefault(version.system_id, []).append(to_dict(version))

        project_system_total = (await db.execute(
            select(func.count()).select_from(TWSystem).where(
                TWSystem.project_id == project_id,
                TWSystem.is_deleted == False,
            )
        )).scalar() or 0
        project_version_total = (await db.execute(
            select(func.count()).select_from(TWVersion).join(
                TWSystem, TWSystem.id == TWVersion.system_id,
            ).where(
                TWVersion.project_id == project_id,
                TWVersion.is_deleted == False,
                TWSystem.is_deleted == False,
            )
        )).scalar() or 0
        items = []
        for system in systems:
            item = to_dict(system)
            item["versions"] = versions_by_system.get(system.id, [])
            item["version_count"] = version_counts.get(system.id, 0)
            items.append(item)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "project_system_total": project_system_total,
            "project_version_total": project_version_total,
        }

    asset_configs = {
        "requirement": (TWRequirement, "confirm_status"),
        "completed_requirement": (TWCompletedRequirement, "confirm_status"),
        "merged_requirement": (TWMergedRequirement, "confirm_status"),
        "test_case": (TWTestCase, "execution_status"),
        "bug": (TWBugRecord, "status"),
        "legacy_item": (TWLegacyItem, "status"),
    }
    if asset_type == "system":
        conditions = [TWSystem.project_id == project_id, TWSystem.is_deleted == False]
        if system_ids:
            conditions.append(TWSystem.id.in_(system_ids))
        elif system_id:
            conditions.append(TWSystem.id == system_id)
        if name:
            conditions.append(TWSystem.name.like(f"%{name}%"))
        if item_type:
            conditions.append(TWSystem.type.like(f"%{item_type}%"))
        _append_created_at_filters(conditions, TWSystem.created_at, created_from, created_to)
        total = (await db.execute(select(func.count()).select_from(TWSystem).where(*conditions))).scalar() or 0
        rows = (await db.execute(
            select(TWSystem, User.real_name.label("creator_real_name"), User.nick_name.label("creator_nick_name"))
            .outerjoin(User, User.id == TWSystem.created_by)
            .where(*conditions)
            .order_by(TWSystem.created_at.desc(), TWSystem.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).all()
        items = []
        for system, creator_real_name, creator_nick_name in rows:
            item = to_dict(system)
            item["creator_name"] = creator_real_name or creator_nick_name or ""
            items.append(item)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    if asset_type == "version":
        conditions = [
            TWVersion.project_id == project_id,
            TWVersion.is_deleted == False,
            TWSystem.is_deleted == False,
        ]
        if system_ids:
            conditions.append(TWVersion.system_id.in_(system_ids))
        elif system_id:
            conditions.append(TWVersion.system_id == system_id)
        if version_ids:
            conditions.append(TWVersion.id.in_(version_ids))
        elif version_id:
            conditions.append(TWVersion.id == version_id)
        if version_no:
            conditions.append(TWVersion.version_no.like(f"%{version_no}%"))
        if current_stage:
            conditions.append(TWVersion.current_stage.like(f"%{current_stage}%"))
        _append_created_at_filters(conditions, TWVersion.created_at, created_from, created_to)
        total = (await db.execute(
            select(func.count()).select_from(TWVersion).join(TWSystem, TWSystem.id == TWVersion.system_id).where(*conditions)
        )).scalar() or 0
        rows = (await db.execute(
            select(
                TWVersion,
                TWSystem.name.label("system_name"),
                User.real_name.label("creator_real_name"),
                User.nick_name.label("creator_nick_name"),
            )
            .join(TWSystem, TWSystem.id == TWVersion.system_id)
            .outerjoin(User, User.id == TWVersion.created_by)
            .where(*conditions)
            .order_by(TWVersion.created_at.desc(), TWVersion.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).all()
        items = []
        for version, system_name, creator_real_name, creator_nick_name in rows:
            item = to_dict(version)
            item["system_name"] = system_name
            item["creator_name"] = creator_real_name or creator_nick_name or ""
            items.append(item)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    config = asset_configs.get(asset_type)
    if not config:
        raise UnifiedException(code=400, message="不支持的资产类型")
    model, status_field = config
    conditions = [
        model.project_id == project_id,
        model.is_deleted == False,
        TWSystem.is_deleted == False,
        TWVersion.is_deleted == False,
    ]
    if system_ids:
        conditions.append(model.system_id.in_(system_ids))
    elif system_id:
        conditions.append(model.system_id == system_id)
    if version_ids:
        conditions.append(model.version_id.in_(version_ids))
    elif version_id:
        conditions.append(model.version_id == version_id)
    if status and asset_type != "test_case":
        if asset_type == "bug" and status == "unclosed":
            # 待办事项：未闭环 Bug（非「已验证关闭」状态）。
            conditions.append(model.status.notin_(["closed", "legacy"]))
        else:
            conditions.append(getattr(model, status_field) == status)
    if assignee_id and asset_type == "bug":
        conditions.append(model.assignee_id == assignee_id)
    if workflow_view:
        if asset_type != "bug" or not current_user_id:
            raise UnifiedException(code=400, message="待办视图仅支持当前用户的 Bug 查询")
        if workflow_view == "pending":
            conditions.extend([model.status == "pending", model.assignee_id == current_user_id])
        elif workflow_view == "verification":
            conditions.extend([
                model.status == "resolved",
                or_(
                    model.verifier_id == current_user_id,
                    and_(model.verifier_id.is_(None), model.created_by == current_user_id),
                ),
            ])
        elif workflow_view == "handled":
            conditions.append(select(TWBugTransition.id).where(
                TWBugTransition.bug_id == model.id,
                TWBugTransition.is_deleted == False,
                TWBugTransition.operated_by == current_user_id,
                TWBugTransition.action.in_(("resolve", "verify", "reactivate")),
            ).exists())
        else:
            raise UnifiedException(code=400, message="待办视图参数不合法")
    if title and asset_type != "test_case":
        conditions.append(model.title.like(f"%{title}%"))
    if item_type and asset_type == "legacy_item":
        conditions.append(model.type.like(f"%{item_type}%"))
    if severity and asset_type == "bug":
        conditions.append(model.severity == severity)
    if merge_status and asset_type == "merged_requirement":
        conditions.append(model.is_stale == (merge_status == "stale"))
    if asset_type == "test_case":
        append_test_case_list_filters(
            conditions,
            status=status,
            confirm_status=confirm_status,
            case_no=case_no,
            title=title,
            source=source,
            priority=priority,
            case_type=case_type,
            created_from=created_from,
            created_to=created_to,
        )
    else:
        _append_created_at_filters(conditions, model.created_at, created_from, created_to)
    total = (await db.execute(
        select(func.count()).select_from(model)
        .join(TWSystem, TWSystem.id == model.system_id)
        .join(TWVersion, TWVersion.id == model.version_id)
        .where(*conditions)
    )).scalar() or 0
    query = (
        select(
            model,
            TWSystem.name.label("system_name"),
            TWVersion.version_no.label("version_no"),
            User.real_name.label("creator_real_name"),
            User.nick_name.label("creator_nick_name"),
        )
        .join(TWSystem, TWSystem.id == model.system_id)
        .join(TWVersion, TWVersion.id == model.version_id)
        .outerjoin(User, User.id == model.created_by)
        .where(*conditions)
    )
    if asset_type == "legacy_item":
        planned_version = aliased(TWVersion)
        query = query.add_columns(planned_version.version_no.label("planned_version_no")).outerjoin(
            planned_version,
            and_(
                planned_version.id == TWLegacyItem.planned_version_id,
                planned_version.is_deleted == False,
            ),
        )
    if asset_type == "bug" and workflow_view == "pending":
        severity_order = case(
            (TWBugRecord.severity == "critical", 1),
            (TWBugRecord.severity == "major", 2),
            else_=3,
        )
        query = query.order_by(severity_order, model.created_at.asc(), model.id.asc())
    elif asset_type == "bug" and workflow_view == "verification":
        query = query.order_by(model.updated_at.asc(), model.id.asc())
    else:
        query = query.order_by(model.updated_at.desc() if workflow_view == "handled" else model.created_at.desc(), model.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    has_requirement_link = asset_type in {"test_case", "bug", "legacy_item"}
    if has_requirement_link:
        query = query.add_columns(TWRequirement.title.label("requirement_title")).outerjoin(
            TWRequirement,
            and_(TWRequirement.id == model.requirement_id, TWRequirement.is_deleted == False),
        )
    if asset_type == "completed_requirement":
        query = query.add_columns(TWRequirement.title.label("source_requirement_title")).outerjoin(
            TWRequirement,
            and_(
                TWRequirement.id == TWCompletedRequirement.source_requirement_id,
                TWRequirement.is_deleted == False,
            ),
        )
    rows = (await db.execute(query)).all()
    bug_user_names: dict[int, str] = {}
    if asset_type == "bug":
        user_ids = {
            user_id for row in rows for user_id in (row[0].assignee_id, row[0].verifier_id, row[0].created_by)
            if user_id
        }
        if user_ids:
            user_rows = (await db.execute(select(User.id, User.real_name, User.nick_name).where(User.id.in_(user_ids)))).all()
            bug_user_names = {item.id: item.real_name or item.nick_name or "" for item in user_rows}
    items = []
    for row in rows:
        asset, system_name, version_no = row[:3]
        item = to_dict(asset)
        item["system_name"] = system_name
        item["version_no"] = version_no
        item["creator_name"] = (getattr(row, "creator_real_name", None) or getattr(row, "creator_nick_name", None) or "")
        if asset_type == "legacy_item":
            item["planned_version_no"] = row.planned_version_no or ""
        if has_requirement_link:
            item["requirement_title"] = row.requirement_title or ""
        if asset_type == "bug":
            item["assignee_name"] = bug_user_names.get(asset.assignee_id, "")
            item["verifier_name"] = bug_user_names.get(asset.verifier_id or asset.created_by, "")
        if asset_type == "completed_requirement":
            item["source_requirement_title"] = row.source_requirement_title or ""
        if asset_type == "merged_requirement":
            item["structure_json"] = normalize_structure(getattr(asset, "structure_json", None))
            # 与 merged_requirement_to_dict 保持一致，列表也下发 is_structured 供前端直接用。
            item["is_structured"] = not structure_is_empty(getattr(asset, "structure_json", None))
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}
