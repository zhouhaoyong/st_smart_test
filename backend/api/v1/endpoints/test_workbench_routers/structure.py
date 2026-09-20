"""项目 / 系统 / 版本管理与作用域看板接口。"""
from __future__ import annotations

import re
from copy import deepcopy

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions import is_super_admin
from core.response import UnifiedException
from core.response import success_response
from core.security import get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import TWProject, TWRequirement, TWSystem, TWVersion, User
from schemas.test_workbench import (
    TWProjectCreate,
    TWProjectBusinessCleanup,
    TWProjectUpdate,
    TWSystemCreate,
    TWSystemUpdate,
    TWVersionCreate,
    TWVersionUpdate,
)
from services.test_workbench_service import (
    can_manage_workbench_project_settings,
    get_owned_project,
    get_project,
    get_project_dashboard_filters,
    get_project_dashboard_stats,
    get_project_business_cleanup_summary,
    get_system,
    get_version,
    assign_requirement_no,
    list_project_dashboard_assets,
    ensure_manage_workbench_record,
    ensure_project_business_cleanup_systems,
    ensure_system_deletable,
    ensure_version_deletable,
    owner_info,
    project_to_dict,
    soft_delete_workbench_project_data,
    soft_delete_project_business_data,
    to_dict,
)
from services.test_workbench_audit import snapshot_workbench_record, soft_delete_workbench_record
from utils.audit_logger import build_project_audit_description, log_operation

from ._shared import _audit_workbench_mutation, ensure_project_unique_value, ensure_system_unique_value

router = APIRouter()


def _compare_version_no(left: str, right: str) -> int:
    left_parts = [int(item) for item in re.findall(r"\d+", left or "")]
    right_parts = [int(item) for item in re.findall(r"\d+", right or "")]
    if not left_parts or not right_parts:
        return 0
    for index in range(max(len(left_parts), len(right_parts))):
        difference = (left_parts[index] if index < len(left_parts) else 0) - (right_parts[index] if index < len(right_parts) else 0)
        if difference:
            return difference
    return 0


async def _lower_version_confirmation(
    db: AsyncSession, system_id: int, version_no: str, exclude_version_id: int | None = None,
) -> dict | None:
    conditions = [TWVersion.system_id == system_id, TWVersion.is_deleted == False]
    if exclude_version_id:
        conditions.append(TWVersion.id != exclude_version_id)
    versions = (await db.execute(select(TWVersion.version_no).where(*conditions))).scalars().all()
    highest_version_no = None
    for existing_version_no in versions:
        if not highest_version_no or _compare_version_no(existing_version_no, highest_version_no) > 0:
            highest_version_no = existing_version_no
    if highest_version_no and _compare_version_no(version_no, highest_version_no) < 0:
        return {
            "requires_confirmation": True,
            "highest_version_no": highest_version_no,
            "message": f"版本号低于当前系统已有最高版本「{highest_version_no}」，仍要保存吗？",
        }
    return None


def _parse_scope_ids(value: str | None) -> list[int] | None:
    if not value:
        return None
    result = [int(item) for item in value.split(",") if item.strip().isdigit() and int(item) > 0]
    return result or None


@router.get("/projects")
async def list_workbench_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    keyword: str | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    visible_condition = True if is_super_admin(current_user) else (
        (TWProject.is_public == True)
        | (TWProject.created_by == current_user.id)
    )
    base = select(TWProject).where(TWProject.is_deleted == False, visible_condition)
    count = select(func.count()).select_from(TWProject).where(TWProject.is_deleted == False, visible_condition)
    if keyword:
        base = base.where(TWProject.name.like(f"%{keyword}%"))
        count = count.where(TWProject.name.like(f"%{keyword}%"))
    total = (await db.execute(count)).scalar() or 0
    rows = (await db.execute(
        base.order_by(TWProject.created_at.desc(), TWProject.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    creator_ids = {row.created_by for row in rows if row.created_by}
    creators = {}
    if creator_ids:
        creator_rows = (await db.execute(select(User).where(User.id.in_(creator_ids)))).scalars().all()
        creators = {user.id: user for user in creator_rows}
    items = []
    for row in rows:
        item = project_to_dict(row)
        item["owner"] = owner_info(creators.get(row.created_by))
        items.append(item)
    return success_response({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/projects")
async def create_workbench_project(data: TWProjectCreate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    project = TWProject(
        name=data.name,
        description=data.description,
        tags=data.tags,
        color=data.color,
        is_public=data.is_public,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    project = (await db.execute(select(TWProject).where(TWProject.id == project.id))).scalar_one()
    await _audit_workbench_mutation(db, current_user, operation="创建", asset_name="项目", record=project)
    return success_response(project_to_dict(project), message="项目创建成功")


@router.get("/projects/{project_id}")
async def get_workbench_project(project_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    project = await get_project(db, project_id, current_user)
    project = (await db.execute(select(TWProject).where(TWProject.id == project.id))).scalar_one()
    item = project_to_dict(project)
    owner = await db.get(User, project.created_by) if project.created_by else None
    item["owner"] = owner_info(owner)
    return success_response(item)


@router.post("/projects/{project_id}/copy")
async def copy_workbench_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """复制项目基础信息、系统、版本和原始需求，不复制 AI 产物及执行类数据。"""
    project = await get_project(db, project_id, current_user)
    base_name = project.name
    all_names = (await db.execute(
        select(TWProject.name).where(
            TWProject.name.like(f"{base_name}\\_%"),
            TWProject.is_deleted == False,
        )
    )).scalars().all()
    max_suffix = 0
    pattern = re.compile(rf"^{re.escape(base_name)}_(\d+)$")
    for name in all_names:
        match = pattern.match(name)
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))
    new_name = f"{base_name}_{max_suffix + 1}"
    if len(new_name) > 100:
        raise UnifiedException(code=400, message=f"复制后项目名「{new_name}」超出100字符限制，无法复制")

    new_project = TWProject(
        name=new_name,
        description=project.description,
        tags=deepcopy(project.tags or []),
        color=project.color,
        is_public=project.is_public,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(new_project)
    await db.flush()

    source_systems = (await db.execute(
        select(TWSystem).where(TWSystem.project_id == project.id, TWSystem.is_deleted == False).order_by(TWSystem.id)
    )).scalars().all()
    system_id_map = {}
    for source in source_systems:
        copied = TWSystem(
            project_id=new_project.id,
            name=source.name,
            type=source.type,
            description=source.description,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(copied)
        await db.flush()
        system_id_map[source.id] = copied.id

    source_versions = (await db.execute(
        select(TWVersion).where(TWVersion.project_id == project.id, TWVersion.is_deleted == False).order_by(TWVersion.id)
    )).scalars().all()
    version_id_map = {}
    for source in source_versions:
        new_system_id = system_id_map.get(source.system_id)
        if not new_system_id:
            continue
        copied = TWVersion(
            project_id=new_project.id,
            system_id=new_system_id,
            version_no=source.version_no,
            description=source.description,
            plan_release_date=source.plan_release_date,
            actual_release_date=source.actual_release_date,
            current_stage=source.current_stage,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(copied)
        await db.flush()
        version_id_map[source.id] = copied.id

    source_requirements = (await db.execute(
        select(TWRequirement).where(TWRequirement.project_id == project.id, TWRequirement.is_deleted == False).order_by(TWRequirement.id)
    )).scalars().all()
    for source in source_requirements:
        new_system_id = system_id_map.get(source.system_id)
        new_version_id = version_id_map.get(source.version_id)
        if not new_system_id or not new_version_id:
            continue
        copied = TWRequirement(
            project_id=new_project.id,
            system_id=new_system_id,
            version_id=new_version_id,
            title=source.title,
            source_type=source.source_type,
            original_content=source.original_content,
            markdown_content=source.markdown_content,
            confirm_status=source.confirm_status,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(copied)
        await db.flush()
        assign_requirement_no(copied, prefix="REQ")

    await db.commit()
    await db.refresh(new_project)
    await _audit_workbench_mutation(
        db,
        current_user,
        operation="复制",
        asset_name="项目",
        record=new_project,
        description=f"复制项目「{project.name}」为「{new_project.name}」，包含其系统、版本和原始需求，不复制 AI 产物及执行类数据",
    )
    return success_response(
        {"id": new_project.id, "name": new_project.name},
        message=f"项目已复制为「{new_project.name}」",
    )


@router.get("/projects/{project_id}/users")
async def list_workbench_project_users(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前项目可见范围内的 Bug 指派候选人，不复用用户管理接口。"""
    await get_project(db, project_id, current_user)
    rows = (await db.execute(
        select(User.id, User.real_name, User.nick_name)
        .where(User.is_deleted == False, User.is_active == True)
        .order_by(User.real_name.asc(), User.id.asc())
    )).all()
    return success_response([
        {"id": user_id, "real_name": real_name, "nick_name": nick_name}
        for user_id, real_name, nick_name in rows
    ])


@router.get("/projects/{project_id}/dashboard")
async def get_workbench_project_dashboard(
    project_id: int,
    system_id: int | None = Query(default=None, description="系统ID，聚焦该系统作用域"),
    version_id: int | None = Query(default=None, description="版本ID，聚焦该版本作用域"),
    system_ids: str | None = Query(default=None, description="多个系统ID，逗号分隔"),
    version_ids: str | None = Query(default=None, description="多个版本ID，逗号分隔"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project(db, project_id, current_user)
    return success_response(await get_project_dashboard_stats(
        db, project_id, system_id=system_id, version_id=version_id,
        system_ids=_parse_scope_ids(system_ids), version_ids=_parse_scope_ids(version_ids), current_user_id=current_user.id,
    ))


def _ensure_project_business_cleanup_permission(current_user: User, project: TWProject) -> None:
    if not is_super_admin(current_user) and not (
        can_manage_workbench_project_settings(current_user, project)
        and not project.is_public
    ):
        raise UnifiedException(code=403, message="权限不足")


@router.get("/projects/{project_id}/business-cleanup-summary")
async def get_workbench_project_business_cleanup_summary(
    project_id: int,
    system_ids: str | None = Query(default=None, description="多个系统ID，逗号分隔"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, project_id, current_user)
    _ensure_project_business_cleanup_permission(current_user, project)
    selected_system_ids = _parse_scope_ids(system_ids)
    if not selected_system_ids:
        raise UnifiedException(code=400, message="请至少选择一个系统")
    await ensure_project_business_cleanup_systems(db, project_id, selected_system_ids)
    return success_response(await get_project_business_cleanup_summary(db, project_id, selected_system_ids))


@router.post("/projects/{project_id}/clear-business-data")
async def clear_workbench_project_business_data(
    project_id: int,
    data: TWProjectBusinessCleanup,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, project_id, current_user)
    _ensure_project_business_cleanup_permission(current_user, project)
    await ensure_project_business_cleanup_systems(db, project_id, data.system_ids)
    summary = await soft_delete_project_business_data(
        db, project_id, current_user.id, beijing_now(), data.system_ids, data.asset_types,
    )
    await db.commit()
    summary_labels = (
        ("system_count", "系统", "个"),
        ("version_count", "版本", "个"),
        ("requirement_count", "需求", "条"),
        ("test_case_count", "测试用例", "条"),
        ("test_execution_count", "执行记录", "条"),
        ("bug_count", "Bug", "条"),
        ("bug_transition_count", "Bug流转记录", "条"),
        ("legacy_item_count", "遗留项", "条"),
    )
    summary_text = "、".join(
        f"{summary.get(key, 0)}{unit}{label}"
        for key, label, unit in summary_labels
        if summary.get(key, 0)
    ) or "0条数据"
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=getattr(current_user, "real_name", "") or getattr(current_user, "nick_name", "") or "未知用户",
        module="test_workbench",
        operation="清空项目数据",
        target_id=project.id,
        target_name=project.name,
        description=build_project_audit_description(
            project.name,
            f"清空所选系统下的业务数据，其中包含{summary_text}",
        ),
        details={"system_ids": data.system_ids, "asset_types": data.asset_types, "summary": summary},
    )
    return success_response(summary, message="项目业务数据已清空")


@router.get("/projects/{project_id}/dashboard-assets")
async def list_workbench_project_dashboard_assets(
    project_id: int,
    asset_type: str = Query(..., description="资产类型"),
    system_id: int | None = Query(default=None, description="系统ID"),
    version_id: int | None = Query(default=None, description="版本ID"),
    system_ids: str | None = Query(default=None, description="多个系统ID，逗号分隔"),
    version_ids: str | None = Query(default=None, description="多个版本ID，逗号分隔"),
    status: str | None = Query(default=None, description="状态"),
    confirm_status: str | None = Query(default=None, description="用例确认状态（draft/confirmed），仅用例列表三 tab 使用"),
    assigned_to_me: bool = Query(default=False, description="仅查询指派给当前用户的 Bug"),
    workflow_view: str | None = Query(default=None, description="我的待办视图：pending/verification/handled"),
    name: str | None = Query(default=None, description="系统名称"),
    version_no: str | None = Query(default=None, description="版本号"),
    case_no: str | None = Query(default=None, description="用例编号"),
    title: str | None = Query(default=None, description="标题"),
    source: str | None = Query(default=None, description="用例来源"),
    priority: str | None = Query(default=None, description="用例优先级"),
    case_type: str | None = Query(default=None, description="用例类型"),
    item_type: str | None = Query(default=None, description="系统或遗留项类型"),
    current_stage: str | None = Query(default=None, description="版本当前阶段"),
    severity: str | None = Query(default=None, description="Bug 严重程度"),
    merge_status: str | None = Query(default=None, description="合并需求状态（merged/stale）"),
    assignee_id: int | None = Query(default=None, description="Bug 处理人 ID"),
    created_from: str | None = Query(default=None, description="创建日期起始，YYYY-MM-DD"),
    created_to: str | None = Query(default=None, description="创建日期结束，YYYY-MM-DD"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project(db, project_id, current_user)
    result = await list_project_dashboard_assets(
        db=db,
        project_id=project_id,
        asset_type=asset_type,
        system_id=system_id,
        version_id=version_id,
        system_ids=_parse_scope_ids(system_ids),
        version_ids=_parse_scope_ids(version_ids),
        status=status,
        confirm_status=confirm_status,
        name=name,
        version_no=version_no,
        case_no=case_no,
        title=title,
        source=source,
        priority=priority,
        case_type=case_type,
        item_type=item_type,
        current_stage=current_stage,
        severity=severity,
        merge_status=merge_status,
        assignee_id=current_user.id if assigned_to_me else assignee_id,
        workflow_view=workflow_view,
        current_user_id=current_user.id,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )
    result.update(await get_project_dashboard_filters(db, project_id))
    return success_response(result)


@router.put("/projects/{project_id}")
async def update_workbench_project(project_id: int, data: TWProjectUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    project = await get_owned_project(db, project_id, current_user)
    before = snapshot_workbench_record(project)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.updated_by = current_user.id
    await db.commit()
    await db.refresh(project)
    project = (await db.execute(select(TWProject).where(TWProject.id == project.id))).scalar_one()
    await _audit_workbench_mutation(db, current_user, operation="编辑", asset_name="项目", record=project, before=before)
    return success_response(project_to_dict(project), message="项目更新成功")


@router.delete("/projects/{project_id}")
async def delete_workbench_project(project_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    project = await get_owned_project(db, project_id, current_user)
    before = snapshot_workbench_record(project)
    await soft_delete_workbench_project_data(db, project, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_mutation(
        db,
        current_user,
        operation="删除",
        asset_name="项目",
        record=project,
        before=before,
        description=f"删除项目：{project.name}",
    )
    return success_response(message="项目删除成功")


@router.get("/systems")
async def list_workbench_systems(project_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await get_project(db, project_id, current_user)
    rows = (await db.execute(select(TWSystem).where(TWSystem.project_id == project_id, TWSystem.is_deleted == False).order_by(TWSystem.created_at.desc(), TWSystem.id.desc()))).scalars().all()
    return success_response([to_dict(row) for row in rows])


@router.post("/systems")
async def create_workbench_system(data: TWSystemCreate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await get_project(db, data.project_id, current_user)
    await ensure_project_unique_value(db, TWSystem, data.project_id, "name", data.name, "系统名称")
    system = TWSystem(**data.model_dump(), created_by=current_user.id, updated_by=current_user.id)
    db.add(system)
    await db.commit()
    await db.refresh(system)
    await _audit_workbench_mutation(db, current_user, operation="创建", asset_name="系统", record=system)
    return success_response(to_dict(system), message="系统创建成功")


@router.put("/systems/{system_id}")
async def update_workbench_system(system_id: int, data: TWSystemUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    system = await get_system(db, system_id, current_user)
    await ensure_manage_workbench_record(db, current_user, system)
    if data.name is not None:
        await ensure_project_unique_value(db, TWSystem, system.project_id, "name", data.name, "系统名称", system.id)
    before = snapshot_workbench_record(system)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(system, field, value)
    system.updated_by = current_user.id
    await db.commit()
    await db.refresh(system)
    await _audit_workbench_mutation(db, current_user, operation="编辑", asset_name="系统", record=system, before=before)
    return success_response(to_dict(system), message="系统更新成功")


@router.delete("/systems/{system_id}")
async def delete_workbench_system(system_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    system = await get_system(db, system_id, current_user)
    await ensure_manage_workbench_record(db, current_user, system)
    await ensure_system_deletable(db, system.id)
    before = snapshot_workbench_record(system)
    soft_delete_workbench_record(system, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_mutation(db, current_user, operation="删除", asset_name="系统", record=system, before=before)
    return success_response(message="系统删除成功")


@router.get("/versions")
async def list_workbench_versions(system_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await get_system(db, system_id, current_user)
    rows = (await db.execute(select(TWVersion).where(TWVersion.system_id == system_id, TWVersion.is_deleted == False).order_by(TWVersion.created_at.desc(), TWVersion.id.desc()))).scalars().all()
    return success_response([to_dict(row) for row in rows])


@router.post("/versions")
async def create_workbench_version(data: TWVersionCreate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    system = await get_system(db, data.system_id, current_user)
    await get_project(db, system.project_id, current_user)
    await ensure_system_unique_value(db, TWVersion, system.id, "version_no", data.version_no, "版本号")
    confirmation = await _lower_version_confirmation(db, system.id, data.version_no)
    if confirmation and not data.confirm_lower_version:
        return success_response(confirmation)
    version_data = data.model_dump(exclude={"confirm_lower_version"})
    version_data["project_id"] = system.project_id
    version = TWVersion(**version_data, created_by=current_user.id, updated_by=current_user.id)
    db.add(version)
    await db.commit()
    await db.refresh(version)
    await _audit_workbench_mutation(db, current_user, operation="创建", asset_name="版本", record=version)
    return success_response(to_dict(version), message="版本创建成功")


@router.put("/versions/{version_id}")
async def update_workbench_version(version_id: int, data: TWVersionUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    version = await get_version(db, version_id, current_user)
    await ensure_manage_workbench_record(db, current_user, version)
    if data.version_no is not None:
        await ensure_system_unique_value(db, TWVersion, version.system_id, "version_no", data.version_no, "版本号", version.id)
        if data.version_no != version.version_no:
            confirmation = await _lower_version_confirmation(db, version.system_id, data.version_no, version.id)
            if confirmation and not data.confirm_lower_version:
                return success_response(confirmation)
    before = snapshot_workbench_record(version)
    for field, value in data.model_dump(exclude={"confirm_lower_version"}, exclude_unset=True).items():
        setattr(version, field, value)
    version.updated_by = current_user.id
    await db.commit()
    await db.refresh(version)
    await _audit_workbench_mutation(db, current_user, operation="编辑", asset_name="版本", record=version, before=before)
    return success_response(to_dict(version), message="版本更新成功")


@router.delete("/versions/{version_id}")
async def delete_workbench_version(version_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    version = await get_version(db, version_id, current_user)
    await ensure_manage_workbench_record(db, current_user, version)
    await ensure_version_deletable(db, version.id)
    before = snapshot_workbench_record(version)
    soft_delete_workbench_record(version, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_mutation(db, current_user, operation="删除", asset_name="版本", record=version, before=before)
    return success_response(message="版本删除成功")
