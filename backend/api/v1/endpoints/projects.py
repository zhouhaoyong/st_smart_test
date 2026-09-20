"""
Project management endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, or_, case
from sqlalchemy.orm import selectinload
from typing import List
from db.session import get_db
from models.models import Project, User, InterfaceCollection, TestCase, Environment, Interface, ExecutionSet, ParameterSet, Report
from core.security import get_current_active_user
from core.response import success_response, UnifiedException
from core.timezone import beijing_now
from pydantic import BaseModel
from datetime import datetime, timezone
from utils.audit_logger import log_operation, log_user_operation
from utils.oss_client import resolve_file_url
from services.proxy_config import legacy_proxy_fields, normalize_proxy_config
from services.service_config import normalize_service_config
from services.api_project_cleanup import (
    get_api_project_business_cleanup_summary,
    soft_delete_api_project_business_data,
)
from services.api_test_workflow import (
    INTERFACE_STATUS_DONE,
    TEST_CASE_CONFIRM_CONFIRMED,
    build_workflow_metrics,
)
from core.permissions import (
    ensure_project_access,
    ensure_project_asset_manage,
    ensure_project_business_cleanup,
    ensure_project_settings_manage,
    is_super_admin,
)

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    tags: list = []
    color: str | None = None
    is_public: bool = False


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list | None = None
    color: str | None = None
    is_public: bool | None = None


class ProjectBusinessCleanup(BaseModel):
    """API 测试项目数据清理请求。"""
    asset_types: list[str]


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    tags: list = []
    owner_id: int
    is_public: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner: dict | None = None

    class Config:
        from_attributes = True


def _owner_info(user):
    if not user:
        return None
    return {"id": user.id, "real_name": user.real_name, "nick_name": user.nick_name, "avatar": resolve_file_url(user.avatar)}


@router.get("/")
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Project).options(selectinload(Project.owner)).where(Project.is_deleted == False)
    count_query = select(func.count()).select_from(Project).where(Project.is_deleted == False)
    if not is_super_admin(current_user):
        visibility = or_(Project.is_public.is_(True), Project.owner_id == getattr(current_user, "id", None))
        query = query.where(visibility)
        count_query = count_query.where(visibility)
    if search:
        query = query.where(Project.name.like(f"%{search}%"))
        count_query = count_query.where(Project.name.like(f"%{search}%"))
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Project.created_at.desc(), Project.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    projects = result.scalars().all()

    data = []
    for p in projects:
        d = {c.name: getattr(p, c.name) for c in p.__table__.columns}
        d["owner"] = _owner_info(p.owner)
        data.append(d)

    return success_response(data={"items": data, "total": total})


@router.post("/")
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    # 检查项目名称是否重复
    existing = (await db.execute(select(Project).where(Project.name == project_data.name, Project.is_deleted == False))).scalars().first()
    if existing:
        raise UnifiedException(code=400, message="项目名称已存在")

    db_project = Project(
        name=project_data.name,
        description=project_data.description,
        tags=project_data.tags,
        color=project_data.color,
        owner_id=current_user.id,
        is_public=project_data.is_public,
    )
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="project",
        operation="create",
        target_id=db_project.id,
        target_name=db_project.name,
        description=f"创建项目：{db_project.name}",
    )

    return success_response(data={
        "id": db_project.id, "name": db_project.name,
        "description": db_project.description, "tags": db_project.tags,
        "owner_id": db_project.owner_id, "is_public": db_project.is_public,
        "created_at": str(db_project.created_at), "updated_at": str(db_project.updated_at),
        "owner": _owner_info(db_project.owner),
    }, message="项目创建成功")


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Project).options(selectinload(Project.owner)).where(Project.id == project_id, Project.is_deleted == False))
    project = result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)

    d = {c.name: getattr(project, c.name) for c in project.__table__.columns}
    d["owner"] = _owner_info(project.owner)
    return success_response(data=d)


@router.put("/{project_id}")
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Project).options(selectinload(Project.owner)).where(Project.id == project_id, Project.is_deleted == False))
    project = result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")

    ensure_project_settings_manage(current_user, project)

    # 如果修改了名称，检查是否重复
    if project_data.name and project_data.name != project.name:
        existing = (await db.execute(select(Project).where(Project.name == project_data.name, Project.is_deleted == False))).scalars().first()
        if existing:
            raise UnifiedException(code=400, message="项目名称已存在")

    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="project",
        operation="update",
        target_id=project.id,
        target_name=project.name,
        description=f"更新项目：{project.name}",
    )

    d = {c.name: getattr(project, c.name) for c in project.__table__.columns}
    d["owner"] = _owner_info(project.owner)
    return success_response(data=d, message="项目更新成功")


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")

    ensure_project_settings_manage(current_user, project)

    # 检查项目下是否有关联数据，有则不允许删除
    env_count = (await db.execute(
        select(func.count()).select_from(Environment).where(Environment.project_id == project_id, Environment.is_deleted == False)
    )).scalar() or 0
    iface_count = (await db.execute(
        select(func.count()).select_from(Interface).join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .where(InterfaceCollection.project_id == project_id, Interface.is_deleted == False, InterfaceCollection.is_deleted == False)
    )).scalar() or 0
    tc_count = (await db.execute(
        select(func.count()).select_from(TestCase).where(TestCase.project_id == project_id, TestCase.is_deleted == False)
    )).scalar() or 0
    collection_count = (await db.execute(
        select(func.count()).select_from(InterfaceCollection).where(
            InterfaceCollection.project_id == project_id,
            InterfaceCollection.is_deleted == False,
        )
    )).scalar() or 0
    execution_set_count = (await db.execute(
        select(func.count()).select_from(ExecutionSet).where(
            ExecutionSet.project_id == project_id,
            ExecutionSet.is_deleted == False,
        )
    )).scalar() or 0
    parameter_set_count = (await db.execute(
        select(func.count()).select_from(ParameterSet).where(
            ParameterSet.project_id == project_id,
            ParameterSet.is_deleted == False,
        )
    )).scalar() or 0
    report_count = (await db.execute(
        select(func.count()).select_from(Report).where(
            Report.project_id == project_id,
            Report.is_deleted == False,
        )
    )).scalar() or 0
    if any((env_count, iface_count, tc_count, collection_count, execution_set_count, parameter_set_count, report_count)):
        parts = []
        if env_count: parts.append(f"{env_count}个环境")
        if iface_count: parts.append(f"{iface_count}个接口")
        if tc_count: parts.append(f"{tc_count}个用例")
        if collection_count: parts.append(f"{collection_count}个接口集")
        if execution_set_count: parts.append(f"{execution_set_count}个执行集")
        if parameter_set_count: parts.append(f"{parameter_set_count}个参数集")
        if report_count: parts.append(f"{report_count}个报告")
        raise UnifiedException(code=400, message=f"请先删除项目下的{'、'.join(parts)}")

    now = beijing_now()
    project.is_deleted = True
    project.deleted_at = now
    # 级联软删除：用 UPDATE 语句避免懒加载 greenlet 问题
    from sqlalchemy import update
    # 直接包含 project_id 的表
    tables_with_project = ['api_environments', 'api_interface_collections',
                           'api_execution_sets', 'api_reports', 'api_test_cases', 'api_parameter_sets']
    for tbl in tables_with_project:
        await db.execute(text(f"UPDATE {tbl} SET is_deleted=1, deleted_at=:now WHERE project_id=:pid"),
                         {"now": now, "pid": project_id})
    # 通过父表间接关联的子表
    sub_queries = {
        "api_interfaces": "collection_id IN (SELECT id FROM api_interface_collections WHERE project_id=:pid)",
        "api_execution_items": "execution_set_id IN (SELECT id FROM api_execution_sets WHERE project_id=:pid)",
        "api_report_details": "report_id IN (SELECT id FROM api_reports WHERE project_id=:pid)",
        "api_parameter_items": "parameter_set_id IN (SELECT id FROM api_parameter_sets WHERE project_id=:pid)",
        "api_report_send_logs": "report_id IN (SELECT id FROM api_reports WHERE project_id=:pid)",
    }
    for tbl, where_clause in sub_queries.items():
        await db.execute(
            text(f"UPDATE {tbl} SET is_deleted=1, deleted_at=:now WHERE {where_clause}"),
            {"now": now, "pid": project_id})

    await db.commit()

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="project",
        operation="delete",
        target_id=project.id,
        target_name=project.name,
        description=f"删除项目：{project.name}",
    )

    return success_response(message="项目删除成功")


@router.post("/{project_id}/copy")
async def copy_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """复制项目及其下所有环境、接口集、接口、用例"""
    result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    # 生成新项目名：原名称_1, _2, ...
    import re
    base_name = project.name
    # 查询所有以 base_name_ 开头的项目名
    all_names = (await db.execute(
        select(Project.name).where(Project.name.like(f"{base_name}\\_%"), Project.is_deleted == False)
    )).scalars().all()
    max_n = 0
    pattern = re.compile(rf"^{re.escape(base_name)}_(\d+)$")
    for name in all_names:
        m = pattern.match(name)
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    new_name = f"{base_name}_{max_n + 1}"
    if len(new_name) > 100:
        raise UnifiedException(code=400, message=f"复制后项目名「{new_name}」超出100字符限制，无法复制")

    # 创建新项目
    new_project = Project(
        name=new_name,
        description=project.description,
        tags=project.tags,
        color=project.color,
        owner_id=current_user.id,
        is_public=project.is_public,
    )
    db.add(new_project)
    await db.flush()

    # 1. 复制环境
    env_result = await db.execute(
        select(Environment).where(Environment.project_id == project_id, Environment.is_deleted == False)
    )
    environments = list(env_result.scalars().all())
    for env in environments:
        proxy_config = normalize_proxy_config(env.proxy_config, env.proxy_http, env.proxy_https)
        proxy_http, proxy_https = legacy_proxy_fields(proxy_config)
        new_env = Environment(
            project_id=new_project.id,
            name=env.name, base_url=env.base_url, port=env.port, timeout=env.timeout,
            global_variables=env.global_variables, global_headers=env.global_headers,
            token_config=env.token_config, extracted_token=env.extracted_token,
            proxy_config=proxy_config,
            service_config=normalize_service_config(env.service_config),
            proxy_http=proxy_http, proxy_https=proxy_https,
            created_by=current_user.id,
        )
        db.add(new_env)

    # 2. 复制接口集（先创建所有，再更新 parent_id）
    col_old_to_new = {}
    col_result = await db.execute(
        select(InterfaceCollection).where(InterfaceCollection.project_id == project_id, InterfaceCollection.is_deleted == False).order_by(InterfaceCollection.id)
    )
    all_cols = list(col_result.scalars().all())
    for col in all_cols:
        new_col = InterfaceCollection(
            project_id=new_project.id,
            name=col.name, description=col.description,
            parent_id=col.parent_id,  # 临时保留旧 parent_id，稍后更新
            sort_order=col.sort_order,
        )
        db.add(new_col)
        await db.flush()
        col_old_to_new[col.id] = new_col.id
    # 更新 parent_id 映射
    for col in all_cols:
        if col.parent_id and col.parent_id in col_old_to_new:
            new_col_id = col_old_to_new[col.id]
            new_parent_id = col_old_to_new[col.parent_id]
            await db.execute(
                text("UPDATE api_interface_collections SET parent_id=:pid WHERE id=:cid"),
                {"pid": new_parent_id, "cid": new_col_id}
            )

    # 3. 复制接口
    iface_old_to_new = {}
    iface_result = await db.execute(
        select(Interface).where(
            Interface.collection_id.in_(col_old_to_new.keys()),
            Interface.is_deleted == False
        )
    )
    interfaces = list(iface_result.scalars().all())
    for iface in interfaces:
        new_iface = Interface(
            collection_id=col_old_to_new[iface.collection_id],
            name=iface.name, method=iface.method, url=iface.url,
            service_key=iface.service_key,
            description=iface.description, tags=iface.tags,
            query_params=iface.query_params, path_params=iface.path_params,
            body_type=iface.body_type, body_content=iface.body_content,
            headers=iface.headers, pre_script=iface.pre_script, post_script=iface.post_script,
            response_example=iface.response_example,
            workflow_status="pending",
            pending_reason="new",
            created_by=current_user.id, updated_by=current_user.id,
        )
        db.add(new_iface)
        await db.flush()
        iface_old_to_new[iface.id] = new_iface.id

    # 4. 复制用例
    tc_result = await db.execute(
        select(TestCase).where(TestCase.project_id == project_id, TestCase.is_deleted == False)
    )
    test_cases = list(tc_result.scalars().all())
    for tc in test_cases:
        new_interface_id = iface_old_to_new.get(tc.interface_id) if tc.interface_id else None
        new_tc = TestCase(
            project_id=new_project.id,
            interface_id=new_interface_id,
            name=tc.name, description=tc.description,
            priority=tc.priority, owner=tc.owner,
            param_overrides=tc.param_overrides,
            script=tc.script,
            assertions=tc.assertions,
            confirm_status="pending",
            confirm_reason="manual",
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(new_tc)

    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="project",
        operation="copy",
        target_id=new_project.id,
        target_name=new_project.name,
        description=(
            f"复制项目{project.name}为{new_project.name}，新增1个项目、"
            f"{len(environments)}个环境、{len(all_cols)}个接口集、"
            f"{len(interfaces)}个接口、{len(test_cases)}个用例"
        ),
        details={
            "project_count": 1,
            "environment_count": len(environments),
            "collection_count": len(all_cols),
            "interface_count": len(interfaces),
            "test_case_count": len(test_cases),
        },
    )
    return success_response(data={"id": new_project.id, "name": new_project.name}, message=f"项目已复制为「{new_name}」")


@router.get("/{project_id}/dashboard")
async def get_project_dashboard(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """项目数据看板"""
    project_result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)

    # 环境数量
    env_count = (await db.execute(
        select(func.count()).select_from(Environment).where(Environment.project_id == project_id, Environment.is_deleted == False)
    )).scalar() or 0

    # 接口数量和处理状态（通过 interface_collections JOIN）
    iface_count_result = await db.execute(
        select(
            func.count(Interface.id),
            func.coalesce(func.sum(case((Interface.workflow_status == INTERFACE_STATUS_DONE, 1), else_=0)), 0),
        ).select_from(Interface)
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .where(InterfaceCollection.project_id == project_id, Interface.is_deleted == False, InterfaceCollection.is_deleted == False)
    )
    iface_count, iface_done_count = iface_count_result.one()
    iface_metrics = build_workflow_metrics(iface_count, iface_done_count)

    # 用例数量和确认状态
    tc_count_result = await db.execute(
        select(
            func.count(TestCase.id),
            func.coalesce(func.sum(case((TestCase.confirm_status == TEST_CASE_CONFIRM_CONFIRMED, 1), else_=0)), 0),
        ).select_from(TestCase)
        .where(TestCase.project_id == project_id, TestCase.is_deleted == False)
    )
    tc_count, tc_confirmed_count = tc_count_result.one()
    tc_metrics = build_workflow_metrics(tc_count, tc_confirmed_count)

    # 执行集数量
    es_count = (await db.execute(
        select(func.count()).select_from(ExecutionSet).where(ExecutionSet.project_id == project_id, ExecutionSet.is_deleted == False)
    )).scalar() or 0

    # 用例贡献排行
    result = await db.execute(
        select(TestCase.owner, func.count(TestCase.id).label('count'))
        .where(TestCase.project_id == project_id, TestCase.is_deleted == False)
        .group_by(TestCase.owner)
        .order_by(func.count(TestCase.id).desc())
    )
    contributions = [{"name": row[0] or "未知", "count": row[1]} for row in result.all()]

    # 接口贡献排行（通过 created_by JOIN users）
    iface_contrib_query = (
        select(User.real_name, func.count(Interface.id).label('count'))
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .join(User, Interface.created_by == User.id)
        .where(InterfaceCollection.project_id == project_id, Interface.is_deleted == False, InterfaceCollection.is_deleted == False)
        .group_by(User.real_name)
        .order_by(func.count(Interface.id).desc())
    )
    iface_result = await db.execute(iface_contrib_query)
    iface_contributions = [{"name": row[0], "count": row[1]} for row in iface_result.all()]

    return success_response(data={
        "environment_count": env_count,
        "interface_count": iface_count,
        "interface_done_count": iface_metrics["completed_count"],
        "interface_pending_count": iface_metrics["pending_count"],
        "interface_process_rate": iface_metrics["rate"],
        "test_case_count": tc_count,
        "test_case_confirmed_count": tc_metrics["completed_count"],
        "test_case_pending_count": tc_metrics["pending_count"],
        "test_case_confirm_rate": tc_metrics["rate"],
        "execution_set_count": es_count,
        "case_contributions": contributions,
        "iface_contributions": iface_contributions,
    })


@router.get("/{project_id}/business-cleanup-summary")
async def get_project_business_cleanup_summary(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 API 测试项目数据清理预览。"""
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_business_cleanup(current_user, project)
    return success_response(data=await get_api_project_business_cleanup_summary(db, project_id))


@router.post("/{project_id}/clear-business-data")
async def clear_project_business_data(
    project_id: int,
    data: ProjectBusinessCleanup,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """软删除 API 测试项目选中的业务数据。"""
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_business_cleanup(current_user, project)

    summary = await soft_delete_api_project_business_data(
        db=db,
        project_id=project_id,
        current_user_id=current_user.id,
        deleted_at=beijing_now(),
        asset_types=data.asset_types,
    )
    await db.commit()

    summary_labels = (
        ("environment_count", "环境", "个"),
        ("interface_count", "接口", "个"),
        ("test_case_count", "用例", "个"),
        ("parameter_set_count", "参数集", "个"),
        ("execution_set_count", "执行集", "个"),
        ("report_count", "测试报告", "个"),
    )
    summary_text = "、".join(
        f"{summary.get(key, 0)}{unit}{label}"
        for key, label, unit in summary_labels
        if summary.get(key, 0)
    ) or "0个数据"
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="project",
        operation="清空项目数据",
        target_id=project.id,
        target_name=project.name,
        description=f"项目【{project.name}】清空 API 测试数据，其中包含{summary_text}",
        details={"asset_types": data.asset_types, "summary": summary},
    )
    return success_response(data=summary, message="项目数据已清空")
