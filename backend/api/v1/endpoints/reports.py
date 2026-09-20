"""
Test report endpoints
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from sqlalchemy.orm import joinedload, selectinload
from typing import List
from urllib.parse import urlsplit
from core.config import settings
from db.session import get_db
from models.models import Report, ReportDetail, Project, User, TestCase, MessageChannel, ReportSendLog, ExecutionSet, Interface, InterfaceCollection
from core.security import get_current_active_user
from core.permissions import ensure_project_access, ensure_project_detail_access, ensure_project_asset_manage
from core.response import mask_sensitive_data, mask_sensitive_text, success_response, UnifiedException
from core.timezone import beijing_now, format_beijing
from services.report_sender import send_report_to_configured_channels
from services.collection_tree import build_collection_tree, get_descendant_collection_ids
from utils.audit_logger import build_batch_audit_description, log_user_operation
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


def _format_report_datetime(value: datetime | None) -> str | None:
    return format_beijing(value)


def _parse_collection_ids(value: str | None) -> list[int] | None:
    """解析报告筛选传入的逗号分隔接口集 ID。"""
    if value is None:
        return None
    collection_ids = []
    for item in value.split(","):
        try:
            collection_id = int(item.strip())
        except (TypeError, ValueError):
            continue
        if collection_id > 0 and collection_id not in collection_ids:
            collection_ids.append(collection_id)
    return collection_ids


def _report_detail_payload(
    detail: ReportDetail,
    current_user: User,
    project: Project,
    *,
    reveal_sensitive: bool = False,
) -> dict:
    payload = {
        column.name: getattr(detail, column.name)
        for column in ReportDetail.__table__.columns
    }
    is_manager_user = bool(
        getattr(current_user, "is_manager", False)
        or getattr(current_user, "is_superuser", False)
    )
    if not is_manager_user and not reveal_sensitive:
        for field in ("request_data", "response_data", "expected_response", "actual_response", "diff_result"):
            payload[field] = mask_sensitive_data(payload[field])
            if isinstance(payload[field], dict):
                original_data = getattr(detail, field, None)
                original_data = original_data if isinstance(original_data, dict) else {}
                for text_field in ("body", "text"):
                    if text_field in payload[field]:
                        original_value = original_data.get(text_field)
                        payload[field][text_field] = (
                            mask_sensitive_text(original_value)
                            if isinstance(original_value, str)
                            else mask_sensitive_data(original_value)
                        )
        if payload.get("logs"):
            payload["logs"] = mask_sensitive_text(payload["logs"])
    return payload


class ReportResponse(BaseModel):
    """报告响应模型"""
    id: int
    name: str
    project_id: int
    execution_set_id: int | None = None
    status: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: int | None = None
    total_steps: int
    passed_steps: int
    failed_steps: int
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    pass_rate: float
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class ReportDetailResponse(BaseModel):
    """报告详情响应模型"""
    id: int
    report_id: int
    step_order: int
    test_step_id: int | None = None
    test_case_id: int | None = None
    status: str
    request_data: dict | None = None
    response_data: dict | None = None
    expected_response: dict | None = None
    actual_response: dict | None = None
    diff_result: list | dict | None = None
    logs: str | None = None
    duration: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


@router.get("/")
async def list_reports(
    project_id: int,
    execution_set_id: int | None = None,
    name: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定项目的报告列表"""
    project_result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)

    query = select(Report).options(
        joinedload(Report.execution_set).joinedload(ExecutionSet.environment)
    ).where(Report.project_id == project_id, Report.is_deleted == False)
    count_query = select(func.count()).select_from(Report).where(Report.project_id == project_id, Report.is_deleted == False)
    if name:
        query = query.where(Report.name.contains(name))
        count_query = count_query.where(Report.name.contains(name))
    if execution_set_id is not None:
        query = query.where(Report.execution_set_id == execution_set_id)
        count_query = count_query.where(Report.execution_set_id == execution_set_id)
    if status and status != 'all':
        query = query.where(Report.status == status)
        count_query = count_query.where(Report.status == status)
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Report.created_at.desc(), Report.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    reports = result.unique().scalars().all()

    items = []
    for r in reports:
        d = {c.name: getattr(r, c.name) for c in r.__table__.columns}
        es = r.execution_set
        d["environment_name"] = es.environment.name if (es and es.environment) else ("环境已删除" if es else None)
        d["execution_set_name"] = es.name if es else None
        d["execution_mode"] = r.execution_mode or (es.execution_mode if es else "serial")
        items.append(d)

    return success_response(data={"items": items, "total": total})


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定报告信息"""
    result = await db.execute(
        select(Report)
        .options(joinedload(Report.execution_set).joinedload(ExecutionSet.environment))
        .where(Report.id == report_id, Report.is_deleted == False)
    )
    report = result.unique().scalar_one_or_none()

    if not report:
        raise UnifiedException(code=400, message="报告不存在")
    project_result = await db.execute(select(Project).where(Project.id == report.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    ensure_project_detail_access(current_user, project)

    d = {c.name: getattr(report, c.name) for c in report.__table__.columns}
    es = report.execution_set
    d["environment_name"] = es.environment.name if (es and es.environment) else ("环境已删除" if es else None)
    d["execution_set_name"] = es.name if es else None
    d["execution_mode"] = report.execution_mode or (es.execution_mode if es else "serial")
    return success_response(data=d)


@router.get("/{report_id}/details")
async def get_report_details(
    report_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取报告步骤详情"""
    report_result = await db.execute(select(Report).where(Report.id == report_id, Report.is_deleted == False))
    report = report_result.scalar_one_or_none()
    if not report:
        raise UnifiedException(code=400, message="报告不存在")
    project_result = await db.execute(select(Project).where(Project.id == report.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    ensure_project_detail_access(current_user, project)

    query = (
        select(ReportDetail)
        .options(
            selectinload(ReportDetail.test_case)
            .selectinload(TestCase.interface)
            .selectinload(Interface.collection)
        )
        .where(ReportDetail.report_id == report_id, ReportDetail.is_deleted == False)
        .order_by(ReportDetail.step_order)
    )
    result = await db.execute(query)
    details = result.unique().scalars().all()

    return success_response(data=[_report_detail_payload(detail, current_user, project, reveal_sensitive=True) for detail in details])


@router.get("/{report_id}/grouped-details")
async def get_report_grouped_details(
    report_id: int,
    name: str | None = None,
    status: str | None = None,
    interface_collection_id: int | None = None,
    interface_collection_ids: str | None = None,
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取按用例分组的报告详情"""
    report_result = await db.execute(select(Report).where(Report.id == report_id, Report.is_deleted == False))
    report = report_result.scalar_one_or_none()
    if not report:
        raise UnifiedException(code=400, message="报告不存在")
    project_result = await db.execute(select(Project).where(Project.id == report.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    ensure_project_detail_access(current_user, project)

    limit = min(max(limit, 1), 100)
    skip = max(skip, 0)

    collection_result = await db.execute(
        select(InterfaceCollection).where(
            InterfaceCollection.project_id == project.id,
            InterfaceCollection.is_deleted == False,
        ).order_by(InterfaceCollection.sort_order, InterfaceCollection.id)
    )
    project_collections = collection_result.scalars().all()
    project_collection_ids = {collection.id for collection in project_collections}
    collection_filter_value = (
        interface_collection_ids
        if interface_collection_ids is not None
        else (str(interface_collection_id) if interface_collection_id is not None else None)
    )
    has_collection_filter = bool(collection_filter_value and collection_filter_value.strip())
    requested_collection_ids = _parse_collection_ids(collection_filter_value)
    resolved_collection_ids = None
    if has_collection_filter and requested_collection_ids is not None:
        valid_collection_ids = [
            collection_id
            for collection_id in requested_collection_ids
            if collection_id in project_collection_ids
        ]
        resolved_collection_ids = await get_descendant_collection_ids(
            db,
            valid_collection_ids,
            project_id=project.id,
        ) if valid_collection_ids else []

    group_key = func.coalesce(ReportDetail.test_case_id, 0).label("group_key")
    passed_expr = func.sum(case((ReportDetail.status == "success", 1), else_=0)).label("passed")
    failed_expr = func.sum(case((ReportDetail.status == "success", 0), else_=1)).label("failed")
    first_step_expr = func.min(ReportDetail.step_order).label("first_step_order")

    group_query = (
        select(group_key, passed_expr, failed_expr, first_step_expr)
        .outerjoin(TestCase, ReportDetail.test_case_id == TestCase.id)
        .outerjoin(Interface, TestCase.interface_id == Interface.id)
        .where(ReportDetail.report_id == report_id, ReportDetail.is_deleted == False)
    )
    if name:
        group_query = group_query.where(TestCase.name.contains(name))
    if has_collection_filter:
        group_query = group_query.where(
            Interface.collection_id.in_(resolved_collection_ids or [-1])
        )

    group_query = group_query.group_by(group_key)

    # 统计卡片口径：只叠加用例名称、接口集条件，不叠加状态条件。
    # 卡片本身就是这个范围内的状态分布，同时又是状态筛选的入口；
    # 若把状态也算进来，点「成功用例」后卡片会变成总数=成功数、失败数=0，卡片就废了。
    scope_subquery = group_query.subquery()
    stats_row = (await db.execute(
        select(
            func.count().label("total_cases"),
            func.coalesce(func.sum(case((scope_subquery.c.failed == 0, 1), else_=0)), 0).label("passed_cases"),
            func.coalesce(func.sum(case((scope_subquery.c.failed > 0, 1), else_=0)), 0).label("failed_cases"),
        ).select_from(scope_subquery)
    )).one()
    scope_total = int(stats_row.total_cases or 0)
    scope_passed = int(stats_row.passed_cases or 0)
    stats = {
        "total_cases": scope_total,
        "passed_cases": scope_passed,
        "failed_cases": int(stats_row.failed_cases or 0),
        "pass_rate": round(scope_passed / scope_total * 100, 2) if scope_total else 0.0,
    }

    if status == "pass":
        group_query = group_query.having(failed_expr == 0)
    elif status == "fail":
        group_query = group_query.having(failed_expr > 0)

    grouped_subquery = group_query.subquery()
    total = (await db.execute(select(func.count()).select_from(grouped_subquery))).scalar() or 0

    page_result = await db.execute(
        select(
            grouped_subquery.c.group_key,
            grouped_subquery.c.passed,
            grouped_subquery.c.failed,
            grouped_subquery.c.first_step_order,
        )
        .order_by(grouped_subquery.c.first_step_order)
        .offset(skip)
        .limit(limit)
    )
    page_groups = page_result.all()
    group_keys = [row.group_key for row in page_groups]

    option_result = await db.execute(
        select(
            Interface.collection_id,
            InterfaceCollection.name,
            func.count(func.distinct(ReportDetail.test_case_id)),
        )
        .select_from(ReportDetail)
        .outerjoin(TestCase, ReportDetail.test_case_id == TestCase.id)
        .outerjoin(Interface, TestCase.interface_id == Interface.id)
        .outerjoin(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .where(
            ReportDetail.report_id == report_id,
            ReportDetail.is_deleted == False,
            Interface.collection_id.isnot(None),
        )
        .group_by(Interface.collection_id, InterfaceCollection.name)
        .order_by(InterfaceCollection.name)
    )
    option_rows = option_result.all()
    collection_options = [
        {"id": row[0], "name": row[1] or "接口集已删除", "count": int(row[2] or 0)}
        for row in option_rows
    ]
    collection_by_id = {collection.id: collection for collection in project_collections}
    available_collection_ids = {
        row[0] for row in option_rows if row[0] in collection_by_id
    }
    pending_collection_ids = list(available_collection_ids)
    while pending_collection_ids:
        collection_id = pending_collection_ids.pop()
        parent_id = collection_by_id[collection_id].parent_id
        if parent_id in collection_by_id and parent_id not in available_collection_ids:
            available_collection_ids.add(parent_id)
            pending_collection_ids.append(parent_id)
    report_collections = [
        collection for collection in project_collections
        if collection.id in available_collection_ids
    ]
    report_collection_counts = {
        row[0]: {
            "total_count": int(row[2] or 0),
            "pending_count": 0,
            "done_count": int(row[2] or 0),
        }
        for row in option_rows
        if row[0] in available_collection_ids
    }
    collection_tree = build_collection_tree(report_collections, report_collection_counts)

    if not group_keys:
        return success_response(data={
            "report_id": report_id,
            "groups": [],
            "total": total,
            "stats": stats,
            "collection_options": collection_options,
            "collection_tree": collection_tree,
        })

    query = (
        select(ReportDetail)
        .options(
            selectinload(ReportDetail.test_case)
            .selectinload(TestCase.interface)
            .selectinload(Interface.collection)
        )
        .where(
            ReportDetail.report_id == report_id,
            ReportDetail.is_deleted == False,
            func.coalesce(ReportDetail.test_case_id, 0).in_(group_keys),
        )
        .order_by(ReportDetail.step_order)
    )
    result = await db.execute(query)
    details = result.unique().scalars().all()

    # 按 test_case_id 分组
    groups_dict = {}
    for d in details:
        tc_id = d.test_case_id
        key = tc_id or 0
        detail_payload = _report_detail_payload(d, current_user, project, reveal_sensitive=True)
        test_case = d.test_case
        interface = test_case.interface if test_case else None

        if key not in groups_dict:
            tc_name = test_case.name if test_case else "未知用例"
            groups_dict[key] = {
                "test_case_id": key if key != 0 else None,
                "test_case_name": tc_name,
                "test_case_deleted": bool(test_case and test_case.is_deleted),
                "passed": 0,
                "failed": 0,
                "interface_id": None,
                "interface_deleted": bool(interface and interface.is_deleted),
                "interface_name": None,
                "interface_method": None,
                "interface_url": None,
                "interface_collection_id": None,
                "interface_collection_name": None,
                "steps": [],
            }

            collection = interface.collection if interface else None
            groups_dict[key].update({
                "interface_id": interface.id if interface else None,
                "interface_name": interface.name if interface else None,
                "interface_method": interface.method if interface else None,
                "interface_url": interface.url if interface else None,
                "interface_collection_id": collection.id if collection else None,
                "interface_collection_name": collection.name if collection else None,
            })

        if d.status == "success":
            groups_dict[key]["passed"] += 1
        else:
            groups_dict[key]["failed"] += 1

        groups_dict[key]["steps"].append({
            "id": d.id,
            "step_order": d.step_order,
            "name": d.test_case.name if d.test_case else "用例执行",
            "status": d.status,
            "interface_id": groups_dict[key]["interface_id"],
            "interface_name": groups_dict[key]["interface_name"],
            "interface_method": groups_dict[key]["interface_method"],
            "interface_url": groups_dict[key]["interface_url"],
            "interface_collection_id": groups_dict[key]["interface_collection_id"],
            "interface_collection_name": groups_dict[key]["interface_collection_name"],
            "request_data": detail_payload["request_data"],
            "response_data": detail_payload["response_data"],
            "expected_response": detail_payload["expected_response"],
            "actual_response": detail_payload["actual_response"],
            "diff_result": detail_payload["diff_result"],
            "logs": detail_payload["logs"],
            "duration": d.duration,
            "retry_attempts": d.retry_attempts or 0,
            "error_message": d.error_message,
        })

    groups = list(groups_dict.values())

    return success_response(data={
        "report_id": report_id,
        "groups": groups,
        "total": total,
        "stats": stats,
        "collection_options": collection_options,
        "collection_tree": collection_tree,
    })


def _base_url_from_referer(referer: str) -> str:
    """从 Referer 还原前端基础地址，保留子路径前缀（如 /tc-smart-test-frontend）。"""
    parts = urlsplit(referer)
    if not parts.scheme or not parts.netloc:
        return ""
    # 哈希路由下 Referer 不含 # 之后的内容，path 即前端部署的基础路径
    path = parts.path or "/"
    segments = [seg for seg in path.split("/") if seg]
    # 末段形如 index.html 时属于入口文件，不算基础路径
    if segments and "." in segments[-1]:
        segments.pop()
    prefix = "/".join(segments)
    return f"{parts.scheme}://{parts.netloc}" + (f"/{prefix}" if prefix else "")


def _get_frontend_url(request: Request) -> str:
    """报告链接使用的前端基础地址。

    优先级：显式配置 FRONTEND_BASE_URL（可带子路径，远程部署场景）
    > Referer 推断（保留子路径）> Origin > Host + 默认端口。
    """
    configured = (settings.FRONTEND_BASE_URL or "").strip()
    if configured:
        return configured.rstrip("/")

    referer_base = _base_url_from_referer(request.headers.get("referer") or "")
    if referer_base:
        return referer_base

    origin = (request.headers.get("origin") or "").strip()
    if "://" in origin:
        scheme, rest = origin.split("://", 1)
        return f"{scheme}://{rest.split('/')[0]}"

    # 回退：用 Host 头 + 前端默认端口
    host = request.headers.get("host") or "localhost"
    host = host.split(":")[0]  # 去掉后端端口
    return f"http://{host}:3000"


@router.post("/{report_id}/send")
async def send_report(
    report_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """发送报告到配置的通知渠道"""
    report = await db.get(Report, report_id)
    if not report or report.is_deleted:
        raise UnifiedException(code=400, message="报告不存在")
    project_result = await db.execute(select(Project).where(Project.id == report.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    if report.status == "running":
        raise UnifiedException(code=400, message="报告仍在执行，请完成后再发送")
    report_name = report.name if report else f"报告#{report_id}"
    try:
        results = await send_report_to_configured_channels(report_id, db, frontend_url=_get_frontend_url(request))
    except ValueError as exc:
        await log_user_operation(
            db=db,
            user=current_user,
            module="report",
            operation="发送",
            target_id=report_id,
            target_name=report_name,
            description="发送报告失败",
            details={"status": "failed"},
            request=request,
        )
        raise UnifiedException(code=400, message=str(exc))
    await log_user_operation(
        db=db,
        user=current_user,
        module="report",
        operation="发送",
        target_id=report_id,
        target_name=report_name,
        description="发送报告",
        details={"status": "success"},
        request=request,
    )
    return success_response(data=results, message="发送完成")


@router.get("/{report_id}/send-logs")
async def get_report_send_logs(
    report_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取报告发送日志"""
    report_result = await db.execute(select(Report).where(Report.id == report_id, Report.is_deleted == False))
    report = report_result.scalar_one_or_none()
    if not report:
        raise UnifiedException(code=400, message="报告不存在")
    project_result = await db.execute(select(Project).where(Project.id == report.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    ensure_project_detail_access(current_user, project)

    result = await db.execute(
        select(ReportSendLog, MessageChannel.group_name)
        .outerjoin(MessageChannel, ReportSendLog.channel_id == MessageChannel.id)
        .where(ReportSendLog.report_id == report_id, ReportSendLog.is_deleted == False)
        .order_by(ReportSendLog.sent_at.desc())
    )
    rows = result.all()
    return success_response(data=[{
        "id": row[0].id,
        "channel_name": row[0].channel_name,
        "group_name": row[1] or row[0].channel_name or "-",
        "status": row[0].status,
        "message_detail": row[0].message_detail,
        "sent_at": _format_report_datetime(row[0].sent_at),
    } for row in rows])


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """软删除报告（同时软删除关联详情和发送日志）"""
    result = await db.execute(select(Report).where(Report.id == report_id, Report.is_deleted == False))
    report = result.scalar_one_or_none()
    if not report:
        raise UnifiedException(code=400, message="报告不存在")
    project_result = await db.execute(select(Project).where(Project.id == report.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    report_name = report.name

    now = beijing_now()
    report.is_deleted = True
    report.deleted_at = now

    # 软删除报告详情
    detail_result = await db.execute(
        select(ReportDetail).where(ReportDetail.report_id == report_id, ReportDetail.is_deleted == False)
    )
    for detail in detail_result.scalars().all():
        detail.is_deleted = True
        detail.deleted_at = now

    # 软删除发送日志
    log_result = await db.execute(
        select(ReportSendLog).where(ReportSendLog.report_id == report_id, ReportSendLog.is_deleted == False)
    )
    for log in log_result.scalars().all():
        log.is_deleted = True
        log.deleted_at = now

    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="report",
        operation="删除",
        target_id=report_id,
        target_name=report_name,
        description="删除报告",
    )
    return success_response(message="报告已删除")


class BatchDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/batch-delete")
async def batch_delete_reports(
    req: BatchDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """批量软删除报告"""
    if not req.ids:
        raise UnifiedException(code=400, message="请选择要删除的报告")

    reports = []
    projects_by_id: dict[int, Project] = {}
    for report_id in dict.fromkeys(req.ids):
        result = await db.execute(select(Report).where(Report.id == report_id, Report.is_deleted == False))
        report = result.scalar_one_or_none()
        if not report:
            continue
        project_result = await db.execute(
            select(Project).where(Project.id == report.project_id, Project.is_deleted == False)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            continue
        ensure_project_asset_manage(current_user, project)
        projects_by_id[report.project_id] = project
        reports.append(report)

    now = beijing_now()
    deleted = 0
    delete_audits: dict[int, dict[str, int | Project]] = {}
    for report in reports:
        report_id = report.id
        report.is_deleted = True
        report.deleted_at = now

        detail_result = await db.execute(
            select(ReportDetail).where(ReportDetail.report_id == report_id, ReportDetail.is_deleted == False)
        )
        details = list(detail_result.scalars().all())
        for detail in details:
            detail.is_deleted = True
            detail.deleted_at = now

        log_result = await db.execute(
            select(ReportSendLog).where(ReportSendLog.report_id == report_id, ReportSendLog.is_deleted == False)
        )
        send_logs = list(log_result.scalars().all())
        for log in send_logs:
            log.is_deleted = True
            log.deleted_at = now
        deleted += 1
        audit = delete_audits.setdefault(
            report.project_id,
            {
                "project": projects_by_id[report.project_id],
                "report_count": 0,
                "detail_count": 0,
                "send_log_count": 0,
            },
        )
        audit["report_count"] += 1
        audit["detail_count"] += len(details)
        audit["send_log_count"] += len(send_logs)

    await db.commit()
    for audit in delete_audits.values():
        project = audit["project"]
        await log_user_operation(
            db=db,
            user=current_user,
            module="report",
            operation="批量删除",
            target_id=project.id,
            target_name=project.name,
            description=build_batch_audit_description(
                project.name,
                "删除",
                "报告",
                int(audit["report_count"]),
                {
                    "报告明细": int(audit["detail_count"]),
                    "发送记录": int(audit["send_log_count"]),
                },
            ),
            details={
                "report_count": int(audit["report_count"]),
                "detail_count": int(audit["detail_count"]),
                "send_log_count": int(audit["send_log_count"]),
            },
        )
    return success_response(data={"deleted": deleted}, message=f"成功删除 {deleted} 个报告")
