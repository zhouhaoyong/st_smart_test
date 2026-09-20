"""
Interface management endpoints
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Annotated, List
from db.session import get_db
from sqlalchemy.orm import joinedload
from models.models import Interface, InterfaceCollection, Project, User, TestCase, ExecutionItem
from core.security import get_current_active_user
from core.response import (
    MASKED_VALUE,
    mask_sensitive_data,
    mask_sensitive_text,
    restore_masked_data,
    restore_masked_text,
    success_response,
    UnifiedException,
)
from core.timezone import beijing_now
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from services.audit_service import (
    get_interface_import_logs,
    get_interface_import_log_items,
    get_interface_import_log_operators,
)
from utils.audit_logger import (
    build_batch_audit_description,
    build_interface_delete_details,
    build_project_audit_description,
    log_interface_import,
    log_operation,
    log_user_operation,
)
from core.permissions import (
    ensure_project_access,
    ensure_project_detail_access,
    ensure_project_asset_manage,
    is_super_admin,
)
from services.collection_tree import get_descendant_collection_ids
from services.api_test_workflow import (
    INTERFACE_STATUS_DONE,
    INTERFACE_STATUS_LABELS,
    INTERFACE_STATUS_PENDING,
    PENDING_REASON_LEGACY,
    PENDING_REASON_LABELS,
    PENDING_REASON_NEW,
    mark_interface_done,
)
from services.interface_case_stats import get_interface_case_stats
from utils.oss_client import resolve_file_url

router = APIRouter()

_INTERFACE_CASE_COUNT_OPERATORS = {"gt", "gte", "eq", "lt", "lte", "ne"}


def _interface_payload(
    interface: Interface,
    current_user: User | None = None,
    *,
    reveal_sensitive: bool = False,
) -> dict:
    creator = getattr(interface, "creator", None)
    modifier = getattr(interface, "modifier", None) or creator
    created_at = getattr(interface, "created_at", None)
    updated_at = getattr(interface, "updated_at", None) or created_at
    payload = {
        "id": interface.id,
        "name": interface.name,
        "method": interface.method,
        "url": interface.url,
        "service_key": interface.service_key,
        "description": interface.description,
        "tags": interface.tags,
        "collection_id": interface.collection_id,
        "query_params": interface.query_params or [],
        "path_params": interface.path_params or [],
        "body_type": interface.body_type,
        "body_content": interface.body_content,
        "body_schema_types": interface.body_schema_types or {},
        "headers": interface.headers or [],
        "pre_script": interface.pre_script,
        "post_script": interface.post_script,
        "response_example": interface.response_example,
        "created_by": interface.created_by,
        "updated_by": getattr(interface, "updated_by", None) or interface.created_by,
        "created_by_name": creator.real_name if creator else None,
        "created_by_avatar": resolve_file_url(getattr(creator, "avatar", None)) if creator else None,
        "updated_by_name": modifier.real_name if modifier else None,
        "updated_by_avatar": resolve_file_url(getattr(modifier, "avatar", None)) if modifier else None,
        "created_at": created_at,
        "updated_at": updated_at,
        "workflow_status": getattr(interface, "workflow_status", INTERFACE_STATUS_PENDING),
        "workflow_status_label": INTERFACE_STATUS_LABELS.get(
            getattr(interface, "workflow_status", INTERFACE_STATUS_PENDING),
            "待处理",
        ),
        "pending_reason": getattr(interface, "pending_reason", None),
        "pending_reason_label": PENDING_REASON_LABELS.get(
            getattr(interface, "pending_reason", None),
        ),
    }
    is_manager_user = bool(
        getattr(current_user, "is_manager", False)
        or getattr(current_user, "is_superuser", False)
    )
    if current_user is not None and not is_manager_user and not reveal_sensitive:
        for field in ("query_params", "path_params", "headers"):
            payload[field] = mask_sensitive_data(payload[field])
        for field in ("body_content", "response_example"):
            payload[field] = mask_sensitive_text(payload[field])
        for field in ("pre_script", "post_script"):
            if payload[field]:
                payload[field] = MASKED_VALUE
    return payload


async def _ensure_interface_manage_permission(db: AsyncSession, interface: Interface, current_user: User) -> Project:
    project = await _get_interface_project(db, interface)
    ensure_project_asset_manage(current_user, project)
    return project


async def _get_interface_project(db: AsyncSession, interface: Interface) -> Project:
    result = await db.execute(
        select(Project)
        .join(InterfaceCollection, InterfaceCollection.project_id == Project.id)
        .where(
            InterfaceCollection.id == interface.collection_id,
            InterfaceCollection.is_deleted == False,
            Project.is_deleted == False,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    return project


class InterfaceCreate(BaseModel):
    """接口创建模型"""
    name: str
    method: str
    url: str
    description: str | None = None
    tags: list = []
    collection_id: int
    query_params: list = []
    path_params: list = []
    body_type: str | None = None
    body_content: str | None = None
    body_schema_types: dict = {}
    headers: list = []
    pre_script: str | None = None
    post_script: str | None = None
    response_example: str | None = None
    source: str | None = None
    service_key: str | None = None


class InterfaceUpdate(BaseModel):
    """接口更新模型"""
    name: str | None = None
    method: str | None = None
    url: str | None = None
    workflow_status: str | None = None
    description: str | None = None
    tags: list | None = None
    collection_id: int | None = None
    query_params: list | None = None
    path_params: list | None = None
    body_type: str | None = None
    body_content: str | None = None
    body_schema_types: dict | None = None
    headers: list | None = None
    pre_script: str | None = None
    post_script: str | None = None
    response_example: str | None = None
    service_key: str | None = None


class InterfaceMoveRequest(BaseModel):
    collection_id: int


class InterfaceBatchMoveRequest(BaseModel):
    interface_ids: list[int] = Field(default_factory=list)
    collection_id: int


class InterfaceResponse(BaseModel):
    """接口响应模型"""
    id: int
    name: str
    method: str
    url: str
    description: str | None = None
    tags: list
    collection_id: int
    query_params: list
    path_params: list
    body_type: str | None = None
    body_content: str | None = None
    body_schema_types: dict = {}
    headers: list
    pre_script: str | None = None
    post_script: str | None = None
    response_example: str | None = None
    service_key: str | None = None
    created_by: int | None = None
    updated_by: int | None = None
    created_by_name: str | None = None
    created_by_avatar: str | None = None
    updated_by_name: str | None = None
    updated_by_avatar: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    workflow_status: str = "pending"
    pending_reason: str | None = None

    class Config:
        from_attributes = True


class InterfaceImportLogCreate(BaseModel):
    """接口管理记录一次 cURL 批量导入的结果摘要。"""
    project_id: int
    source: str
    source_name: str | None = None
    status: str = "success"
    summary: str = "接口导入完成"
    details: dict = Field(default_factory=dict)


def _build_interface_move_summary(
    interface: Interface,
    old_collection_id: int | None,
    new_collection_id: int | None,
    linked_cases: list[TestCase],
    linked_execution_items: list[ExecutionItem],
) -> dict:
    return {
        "interface_id": interface.id,
        "old_collection_id": old_collection_id,
        "new_collection_id": new_collection_id,
        "test_case_count": len(linked_cases),
        "execution_item_count": len(linked_execution_items),
    }


async def _collect_interface_move_links(db: AsyncSession, interface_id: int) -> tuple[list[TestCase], list[ExecutionItem]]:
    case_result = await db.execute(
        select(TestCase).where(
            TestCase.interface_id == interface_id,
            TestCase.is_deleted == False,
        )
    )
    linked_cases = case_result.scalars().all()
    case_ids = [case.id for case in linked_cases]
    if not case_ids:
        return linked_cases, []

    item_result = await db.execute(
        select(ExecutionItem).where(
            ExecutionItem.test_case_id.in_(case_ids),
            ExecutionItem.is_deleted == False,
        )
    )
    return linked_cases, item_result.scalars().all()


def _summarize_batch_move_results(success_ids: list[int], failed: list[dict]) -> dict:
    return {
        "success_ids": success_ids,
        "failed": failed,
        "success_count": len(success_ids),
        "failed_count": len(failed),
    }


@router.get("/")
async def list_interfaces(
    collection_id: int | None = None,
    collection_ids: Annotated[list[int] | None, Query()] = None,
    project_id: int | None = None,
    keyword: str | None = None,
    name: str | None = None,
    url: str | None = None,
    method: str | None = None,
    created_by_name: str | None = None,
    test_case_count_operator: str | None = None,
    test_case_count: int | None = None,
    workflow_status: str | None = None,
    pending_reason: str | None = None,
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取接口列表（可按接口集或项目过滤）"""
    if limit < 1 or limit > 100:
        raise UnifiedException(code=400, message="接口列表每页数量必须在 1 到 100 之间")
    query = (
        select(Interface)
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .join(Project, InterfaceCollection.project_id == Project.id)
        .options(
            joinedload(Interface.collection),
            joinedload(Interface.creator),
            joinedload(Interface.modifier),
        )
        .where(Interface.is_deleted == False, InterfaceCollection.is_deleted == False, Project.is_deleted == False)
    )
    count_query = (
        select(func.count()).select_from(Interface)
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .join(Project, InterfaceCollection.project_id == Project.id)
        .where(Interface.is_deleted == False, InterfaceCollection.is_deleted == False, Project.is_deleted == False)
    )
    if not is_super_admin(current_user):
        visibility = or_(Project.is_public.is_(True), Project.owner_id == current_user.id)
        query = query.where(visibility)
        count_query = count_query.where(visibility)

    if keyword:
        keyword_filter = or_(Interface.name.contains(keyword), Interface.url.contains(keyword))
        query = query.where(keyword_filter)
        count_query = count_query.where(keyword_filter)
    if name:
        query = query.where(Interface.name.contains(name))
        count_query = count_query.where(Interface.name.contains(name))
    if url:
        query = query.where(Interface.url.contains(url))
        count_query = count_query.where(Interface.url.contains(url))
    normalized_method = (method or "").strip().upper()
    if normalized_method:
        query = query.where(func.upper(Interface.method) == normalized_method)
        count_query = count_query.where(func.upper(Interface.method) == normalized_method)
    if created_by_name:
        query = query.join(Interface.creator).where(User.real_name.contains(created_by_name))
        count_query = count_query.join(Interface.creator).where(User.real_name.contains(created_by_name))

    if workflow_status and workflow_status not in {INTERFACE_STATUS_PENDING, INTERFACE_STATUS_DONE}:
        raise UnifiedException(code=400, message="接口状态筛选条件不正确")
    if pending_reason and pending_reason not in PENDING_REASON_LABELS:
        raise UnifiedException(code=400, message="待处理原因筛选条件不正确")
    if workflow_status:
        query = query.where(Interface.workflow_status == workflow_status)
        count_query = count_query.where(Interface.workflow_status == workflow_status)
    if pending_reason:
        query = query.where(Interface.pending_reason == pending_reason)
        count_query = count_query.where(Interface.pending_reason == pending_reason)

    count_operator = (test_case_count_operator or "").strip() or None
    if count_operator and count_operator not in _INTERFACE_CASE_COUNT_OPERATORS:
        raise UnifiedException(code=400, message="用例数筛选条件不正确")
    if (count_operator is None) != (test_case_count is None):
        raise UnifiedException(code=400, message="请同时提供用例数筛选条件和数量")
    if test_case_count is not None and test_case_count < 0:
        raise UnifiedException(code=400, message="用例数量不能小于 0")
    if count_operator is not None and test_case_count is not None:
        case_count = (
            select(func.count(TestCase.id))
            .where(
                TestCase.interface_id == Interface.id,
                TestCase.is_deleted == False,
            )
            .correlate(Interface)
            .scalar_subquery()
        )
        case_count_condition = {
            "gt": case_count > test_case_count,
            "gte": case_count >= test_case_count,
            "eq": case_count == test_case_count,
            "lt": case_count < test_case_count,
            "lte": case_count <= test_case_count,
            "ne": case_count != test_case_count,
        }[count_operator]
        query = query.where(case_count_condition)
        count_query = count_query.where(case_count_condition)

    if collection_ids:
        if project_id is None:
            raise UnifiedException(code=400, message="多选接口集筛选必须提供项目")
        collections = (await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id.in_(collection_ids),
                InterfaceCollection.project_id == project_id,
                InterfaceCollection.is_deleted == False,
            )
        )).scalars().all()
        if len(collections) != len(set(collection_ids)):
            raise UnifiedException(code=400, message="部分接口集不存在或不属于当前项目")
        project_result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
        project = project_result.scalar_one_or_none()
        if not project:
            raise UnifiedException(code=403, message="权限不足")
        ensure_project_access(current_user, project)
        descendant_ids = await get_descendant_collection_ids(
            db, list({collection.id for collection in collections}), project_id=project_id,
        )
        query = query.where(Interface.collection_id.in_(descendant_ids))
        count_query = count_query.where(Interface.collection_id.in_(descendant_ids))
    elif collection_id is not None:
        collection_result = await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id == collection_id,
                InterfaceCollection.is_deleted == False,
            )
        )
        collection = collection_result.scalar_one_or_none()
        if not collection:
            raise UnifiedException(code=400, message="接口集不存在")
        project_result = await db.execute(select(Project).where(Project.id == collection.project_id, Project.is_deleted == False))
        project = project_result.scalar_one_or_none()
        if not project:
            raise UnifiedException(code=403, message="权限不足")
        ensure_project_access(current_user, project)
        collection_ids = await get_descendant_collection_ids(db, [collection_id], project_id=collection.project_id)
        query = query.where(Interface.collection_id.in_(collection_ids))
        count_query = count_query.where(Interface.collection_id.in_(collection_ids))
    elif project_id is not None:
        project_result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
        project = project_result.scalar_one_or_none()
        if not project:
            raise UnifiedException(code=403, message="权限不足")
        ensure_project_access(current_user, project)
        query = query.where(InterfaceCollection.project_id == project_id)
        count_query = count_query.where(InterfaceCollection.project_id == project_id)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Interface.id).offset(skip).limit(limit)
    result = await db.execute(query)
    interfaces = result.unique().scalars().all()

    interface_ids = [interface.id for interface in interfaces]
    case_stats = await get_interface_case_stats(db, interface_ids)

    data = []
    for intf in interfaces:
        item = _interface_payload(intf, current_user)
        item["collection_name"] = intf.collection.name if intf.collection else None
        item.update(case_stats.get(intf.id, {
            "test_case_count": 0,
            "pending_test_case_count": 0,
        }))
        data.append(item)

    return success_response(data={"items": data, "total": total})


@router.get("/methods")
async def list_interface_methods(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前项目接口中实际使用的请求方法。"""
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)

    result = await db.execute(
        select(Interface.method)
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .where(
            InterfaceCollection.project_id == project_id,
            InterfaceCollection.is_deleted == False,
            Interface.is_deleted == False,
            Interface.method.is_not(None),
        )
        .distinct()
        .order_by(Interface.method)
    )
    methods = sorted({str(value).strip().upper() for value in result.scalars().all() if str(value).strip()})
    return success_response(data={"items": methods})


@router.get("/selection-ids")
async def list_interface_selection_ids(
    project_id: int,
    collection_ids: Annotated[list[int] | None, Query()] = None,
    keyword: str | None = None,
    name: str | None = None,
    url: str | None = None,
    test_case_count_operator: str | None = None,
    test_case_count: int | None = None,
    workflow_status: str | None = None,
    pending_reason: str | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """按接口列表筛选条件返回全部接口 ID，供跨分页批量选择使用。"""
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)

    query = (
        select(Interface.id)
        .join(InterfaceCollection, Interface.collection_id == InterfaceCollection.id)
        .join(Project, InterfaceCollection.project_id == Project.id)
        .where(
            InterfaceCollection.project_id == project_id,
            Interface.is_deleted == False,
            InterfaceCollection.is_deleted == False,
        )
    )
    if not is_super_admin(current_user):
        query = query.where(or_(Project.is_public.is_(True), Project.owner_id == current_user.id))
    if keyword:
        query = query.where(or_(Interface.name.contains(keyword), Interface.url.contains(keyword)))
    if name:
        query = query.where(Interface.name.contains(name))
    if url:
        query = query.where(Interface.url.contains(url))

    if workflow_status and workflow_status not in {INTERFACE_STATUS_PENDING, INTERFACE_STATUS_DONE}:
        raise UnifiedException(code=400, message="接口状态筛选条件不正确")
    if pending_reason and pending_reason not in PENDING_REASON_LABELS:
        raise UnifiedException(code=400, message="待处理原因筛选条件不正确")
    if workflow_status:
        query = query.where(Interface.workflow_status == workflow_status)
    if pending_reason:
        query = query.where(Interface.pending_reason == pending_reason)

    count_operator = (test_case_count_operator or "").strip() or None
    if count_operator and count_operator not in _INTERFACE_CASE_COUNT_OPERATORS:
        raise UnifiedException(code=400, message="用例数筛选条件不正确")
    if (count_operator is None) != (test_case_count is None):
        raise UnifiedException(code=400, message="请同时提供用例数筛选条件和数量")
    if test_case_count is not None and test_case_count < 0:
        raise UnifiedException(code=400, message="用例数量不能小于 0")
    if count_operator is not None and test_case_count is not None:
        case_count = (
            select(func.count(TestCase.id))
            .where(TestCase.interface_id == Interface.id, TestCase.is_deleted == False)
            .correlate(Interface)
            .scalar_subquery()
        )
        query = query.where({
            "gt": case_count > test_case_count,
            "gte": case_count >= test_case_count,
            "eq": case_count == test_case_count,
            "lt": case_count < test_case_count,
            "lte": case_count <= test_case_count,
            "ne": case_count != test_case_count,
        }[count_operator])

    if collection_ids:
        collections = (await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id.in_(collection_ids),
                InterfaceCollection.project_id == project_id,
                InterfaceCollection.is_deleted == False,
            )
        )).scalars().all()
        if len(collections) != len(set(collection_ids)):
            raise UnifiedException(code=400, message="部分接口集不存在或不属于当前项目")
        descendant_ids = await get_descendant_collection_ids(
            db, list({collection.id for collection in collections}), project_id=project_id,
        )
        query = query.where(Interface.collection_id.in_(descendant_ids))

    ids = list((await db.execute(query.order_by(Interface.id))).scalars().all())
    return success_response(data={"ids": ids, "total": len(ids)})


def _interface_import_log_payload(log, user_avatar: str | None = None) -> dict:
    details = log.details if isinstance(log.details, dict) else {}
    record_type = details.get("record_type")
    operation = getattr(log, "operation", None)
    # 兼容旧版“当前接口下删除用例”记录：旧数据的接口数为 0，且删除类型明确为 cases。
    is_case_delete_record = (
        record_type == "case_delete_all"
        or operation == "全部删除"
        or (
            record_type == "interface_delete"
            and details.get("delete_type") == "cases"
            and int(details.get("interface_count") or 0) == 0
        )
    )
    is_interface_delete_record = (
        record_type == "interface_delete"
        or (operation == "删除" and not is_case_delete_record)
    )
    is_delete_record = is_case_delete_record or is_interface_delete_record
    if is_delete_record:
        summary_details = {
            key: details[key]
            for key in ("record_type", "delete_type", "status", "interface_count", "case_count", "execution_item_count", "collection_count", "summary")
            if key in details
        }
        if is_case_delete_record:
            summary_details["record_type"] = "case_delete_all"
        summary = details.get("summary") or log.description or (
            "用例删除完成" if is_case_delete_record else "接口删除完成"
        )
        if is_case_delete_record:
            summary = str(summary)
            if summary.startswith("全部删除"):
                summary = f"删除{summary[len('全部删除'):]}"
            elif "内，全部删除" in summary:
                summary = summary.replace("内，全部删除", "内，删除", 1)
        return {
            "id": log.id,
            "record_type": "case_delete_all" if is_case_delete_record else "interface_delete",
            "source": "case_delete_all" if is_case_delete_record else "delete",
            "source_name": None,
            "user_id": log.user_id,
            "user_name": log.user_name,
            "user_avatar": user_avatar,
            "status": details.get("status") or "success",
            "summary": summary,
            # 时间轴只返回汇总，明细列表按点击后的记录 ID 分页查询，避免首屏携带大 JSON。
            "details": summary_details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
    if (
        getattr(log, "module", None) == "interface_case_generate"
        and operation == "确认保存"
    ):
        return {
            "id": log.id,
            "record_type": "interface_case_generate",
            "source": "ai_generate",
            "source_name": None,
            "user_id": log.user_id,
            "user_name": log.user_name,
            "user_avatar": user_avatar,
            "status": details.get("status") or "success",
            "summary": details.get("summary") or log.description or "AI生成用例完成",
            "details": details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
    raw_source = str(details.get("source") or "").strip().lower()
    source = raw_source if raw_source in {"file", "curl", "ai"} else "file"
    return {
        "id": log.id,
        "record_type": "interface_import",
        "source": source,
        # 旧版文件导入把文件名写在 source，新版则单独写 source_name。
        "source_name": details.get("source_name") or (details.get("source") if source == "file" else None),
        "user_id": log.user_id,
        "user_name": log.user_name,
        "user_avatar": user_avatar,
        "status": details.get("status") or "success",
        "summary": details.get("summary") or log.description or "接口导入完成",
        "details": details,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.get("/import-logs")
async def list_interface_import_logs(
    project_id: int,
    skip: int = 0,
    limit: int = 20,
    operation_type: list[str] | None = Query(None),
    user_id: int | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前项目的接口操作时间轴，所有已登录用户均可查看。"""
    logs, total = await get_interface_import_logs(
        db=db,
        project_id=project_id,
        skip=max(skip, 0),
        limit=min(max(limit, 1), 100),
        operation_type=operation_type,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
    )
    user_avatar_map = {}
    user_ids = {log.user_id for log in logs if log.user_id}
    if user_ids:
        user_result = await db.execute(
            select(User.id, User.avatar).where(User.id.in_(user_ids))
        )
        user_avatar_map = {
            row.id: resolve_file_url(row.avatar)
            for row in user_result.all()
        }
    return success_response(data={
        "items": [
            _interface_import_log_payload(log, user_avatar_map.get(log.user_id))
            for log in logs
        ],
        "total": total,
    })


@router.get("/import-logs/operators")
async def list_interface_import_log_operators(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前项目操作记录中的操作人选项，所有已登录用户均可查看。"""
    operators = await get_interface_import_log_operators(db=db, project_id=project_id)
    return success_response(data={"items": operators})


@router.get("/import-logs/{log_id}/items")
async def list_interface_import_log_items(
    log_id: int,
    project_id: int,
    item_type: str = "interfaces",
    keyword: str = "",
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查询接口删除记录中的接口或用例明细，登录用户均可查看。"""
    if item_type not in {"interfaces", "cases"}:
        raise UnifiedException(code=400, message="明细类型不正确")
    items, total = await get_interface_import_log_items(
        db=db,
        project_id=project_id,
        log_id=log_id,
        item_type=item_type,
        keyword=keyword,
        skip=max(skip, 0),
        limit=min(max(limit, 1), 100),
    )
    if items is None:
        raise UnifiedException(code=400, message="删除记录不存在")
    return success_response(data={"items": items, "total": total})


@router.post("/import-logs")
async def create_interface_import_log(
    data: InterfaceImportLogCreate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """写入接口管理侧的 cURL 导入汇总记录；写入仍沿用接口导入权限。"""
    if data.source != "curl":
        raise UnifiedException(code=400, message="仅支持记录 cURL 导入")
    if data.status not in {"success", "partial", "failed"}:
        raise UnifiedException(code=400, message="导入结果状态不正确")

    project = (await db.execute(
        select(Project).where(Project.id == data.project_id, Project.is_deleted == False)
    )).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    await log_interface_import(
        db=db,
        user=current_user,
        project_id=data.project_id,
        project_name=project.name,
        source=data.source,
        status=data.status,
        summary=data.summary,
        source_name=data.source_name,
        details=data.details,
        request=request,
    )
    return success_response(data=None, message="导入日志已记录")


@router.post("/")
async def create_interface(
    interface_data: InterfaceCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新接口"""
    # 验证接口集是否存在
    result = await db.execute(
        select(InterfaceCollection).where(
            InterfaceCollection.id == interface_data.collection_id,
            InterfaceCollection.is_deleted == False,
        )
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise UnifiedException(code=400, message="接口集不存在")
    project_result = await db.execute(select(Project).where(Project.id == collection.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    # 检查同接口集下名称是否重复
    existing = (await db.execute(
        select(Interface).where(
            Interface.collection_id == interface_data.collection_id,
            Interface.name == interface_data.name,
            Interface.is_deleted == False
        )
    )).scalars().first()
    if existing:
        raise UnifiedException(code=400, message="该接口集下接口名称已存在")

    db_interface = Interface(
        name=interface_data.name,
        method=interface_data.method,
        url=interface_data.url,
        description=interface_data.description,
        tags=interface_data.tags,
        source=interface_data.source,
        service_key=interface_data.service_key,
        collection_id=interface_data.collection_id,
        query_params=interface_data.query_params,
        path_params=interface_data.path_params,
        body_type=interface_data.body_type,
        body_content=interface_data.body_content,
        body_schema_types=interface_data.body_schema_types,
        headers=interface_data.headers,
        pre_script=interface_data.pre_script,
        post_script=interface_data.post_script,
        response_example=interface_data.response_example,
        workflow_status=INTERFACE_STATUS_PENDING,
        pending_reason=PENDING_REASON_NEW,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    
    db.add(db_interface)
    await db.commit()
    await db.refresh(db_interface)
    db_interface.creator = current_user
    db_interface.modifier = current_user
    
    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="interface",
        operation="create",
        target_id=db_interface.id,
        target_name=db_interface.name,
        description=build_project_audit_description(project.name, f"创建接口：{db_interface.name}"),
    )
    
    return success_response(data=_interface_payload(db_interface, current_user), message="接口创建成功")


@router.get("/{interface_id}")
async def get_interface(
    interface_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定接口信息"""
    result = await db.execute(
        select(Interface)
        .options(joinedload(Interface.creator), joinedload(Interface.modifier))
        .where(Interface.id == interface_id, Interface.is_deleted == False)
    )
    interface = result.scalar_one_or_none()

    if not interface:
        raise UnifiedException(code=400, message="接口不存在")
    project = await _get_interface_project(db, interface)
    ensure_project_access(current_user, project)
    ensure_project_detail_access(current_user, project)
    
    return success_response(data=_interface_payload(interface, current_user, reveal_sensitive=True))


@router.put("/{interface_id}")
async def update_interface(
    interface_id: int,
    interface_data: InterfaceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新接口信息"""
    result = await db.execute(
        select(Interface)
        .options(joinedload(Interface.creator), joinedload(Interface.modifier))
        .where(Interface.id == interface_id, Interface.is_deleted == False)
    )
    interface = result.scalar_one_or_none()

    if not interface:
        raise UnifiedException(code=400, message="接口不存在")
    await _ensure_interface_manage_permission(db, interface, current_user)
    source_project = await _get_interface_project(db, interface)

    old_collection_id = interface.collection_id
    move_summary = None

    # 仅当名称或所属集合发生变化时才检查重复
    name_changed = interface_data.name is not None and interface_data.name != interface.name
    coll_changed = interface_data.collection_id is not None and interface_data.collection_id != interface.collection_id
    if name_changed or coll_changed:
        new_name = interface_data.name if name_changed else interface.name
        new_collection = interface_data.collection_id if coll_changed else interface.collection_id
        collection_result = await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id == new_collection,
                InterfaceCollection.project_id == source_project.id,
                InterfaceCollection.is_deleted == False,
            )
        )
        if not collection_result.scalar_one_or_none():
            raise UnifiedException(code=400, message="接口集不存在")
        existing = (await db.execute(
            select(Interface).where(
                Interface.id != interface_id,
                Interface.collection_id == new_collection,
                Interface.name == new_name,
                Interface.is_deleted == False
            )
        )).scalars().first()
        if existing:
            raise UnifiedException(code=400, message="该接口集下接口名称已存在")

    # 更新字段
    update_data = interface_data.model_dump(exclude_unset=True)
    if "workflow_status" in update_data:
        workflow_status = update_data.pop("workflow_status")
        if workflow_status not in {INTERFACE_STATUS_PENDING, INTERFACE_STATUS_DONE}:
            raise UnifiedException(code=400, message="接口状态不正确")
        if workflow_status == INTERFACE_STATUS_DONE:
            mark_interface_done(interface)
        else:
            interface.workflow_status = INTERFACE_STATUS_PENDING
            if not interface.pending_reason:
                interface.pending_reason = PENDING_REASON_LEGACY
    is_manager_user = bool(
        getattr(current_user, "is_manager", False)
        or getattr(current_user, "is_superuser", False)
    )
    if not is_manager_user:
        for field in ("query_params", "path_params", "headers"):
            if field in update_data:
                update_data[field] = restore_masked_data(getattr(interface, field), update_data[field])
        for field in ("body_content", "response_example"):
            if field in update_data:
                update_data[field] = restore_masked_text(getattr(interface, field), update_data[field])
        for field in ("pre_script", "post_script"):
            if field in update_data:
                update_data[field] = restore_masked_data(getattr(interface, field), update_data[field])
    for field, value in update_data.items():
        setattr(interface, field, value)
    interface.updated_by = current_user.id
    interface.modifier = current_user

    if coll_changed:
        linked_cases, linked_execution_items = await _collect_interface_move_links(db, interface_id)
        move_summary = _build_interface_move_summary(
            interface=interface,
            old_collection_id=old_collection_id,
            new_collection_id=interface.collection_id,
            linked_cases=linked_cases,
            linked_execution_items=linked_execution_items,
        )
    
    await db.commit()
    await db.refresh(interface)
    interface.modifier = current_user

    # 先构建响应数据再记日志，避免 commit 后访问过期对象
    result = _interface_payload(interface, current_user)
    result["move_summary"] = move_summary

    await log_operation(
        db=db, user_id=current_user.id, user_name=current_user.real_name,
        module="interface", operation="update", target_id=interface.id,
        target_name=interface.name,
        description=build_project_audit_description(source_project.name, f"更新接口：{interface.name}"),
    )

    return success_response(data=result, message="接口更新成功")


@router.post("/batch-move")
async def batch_move_interfaces(
    move_data: InterfaceBatchMoveRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批量移动接口；每条单独提交，单条失败不阻塞其他接口。"""
    interface_ids = list(dict.fromkeys(move_data.interface_ids or []))
    if not interface_ids:
        raise UnifiedException(code=400, message="请选择要移动的接口")

    success_ids = []
    failed = []
    for interface_id in interface_ids:
        try:
            result = await db.execute(
                select(Interface).where(Interface.id == interface_id, Interface.is_deleted == False)
            )
            interface = result.scalar_one_or_none()
            if not interface:
                raise UnifiedException(code=400, message="接口不存在")
            source_project = await _ensure_interface_manage_permission(db, interface, current_user)
            collection_result = await db.execute(
                select(InterfaceCollection).where(
                    InterfaceCollection.id == move_data.collection_id,
                    InterfaceCollection.project_id == source_project.id,
                    InterfaceCollection.is_deleted == False,
                )
            )
            if not collection_result.scalar_one_or_none():
                raise UnifiedException(code=400, message="接口集不存在")
            if move_data.collection_id != interface.collection_id:
                existing = (await db.execute(
                    select(Interface).where(
                        Interface.id != interface_id,
                        Interface.collection_id == move_data.collection_id,
                        Interface.name == interface.name,
                        Interface.is_deleted == False,
                    )
                )).scalars().first()
                if existing:
                    raise UnifiedException(code=400, message="目标接口集下接口名称已存在")
                old_collection_id = interface.collection_id
                interface.collection_id = move_data.collection_id
                await log_operation(
                    db=db,
                    user_id=current_user.id,
                    user_name=current_user.real_name,
                    module="interface",
                    operation="move",
                    target_id=interface.id,
                    target_name=interface.name,
                    description=build_project_audit_description(
                        source_project.name,
                        f"移动接口：{interface.name} ({old_collection_id} -> {interface.collection_id})",
                    ),
                )
                await db.commit()
            success_ids.append(interface_id)
        except UnifiedException as exc:
            await db.rollback()
            failed.append({"interface_id": interface_id, "message": exc.message})
        except Exception as exc:
            await db.rollback()
            failed.append({"interface_id": interface_id, "message": str(exc) or "移动失败"})

    summary = _summarize_batch_move_results(success_ids, failed)
    message = f"批量移动完成：成功 {summary['success_count']} 个，失败 {summary['failed_count']} 个"
    return success_response(data=summary, message=message)


@router.post("/{interface_id}/move")
async def move_interface(
    interface_id: int,
    move_data: InterfaceMoveRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """移动接口到指定接口集；用例和执行项继续通过接口/用例关系引用。"""
    result = await db.execute(select(Interface).where(Interface.id == interface_id, Interface.is_deleted == False))
    interface = result.scalar_one_or_none()
    if not interface:
        raise UnifiedException(code=400, message="接口不存在")
    await _ensure_interface_manage_permission(db, interface, current_user)
    source_project = await _get_interface_project(db, interface)

    collection_result = await db.execute(
        select(InterfaceCollection).where(
            InterfaceCollection.id == move_data.collection_id,
            InterfaceCollection.project_id == source_project.id,
            InterfaceCollection.is_deleted == False,
        )
    )
    if not collection_result.scalar_one_or_none():
        raise UnifiedException(code=400, message="接口集不存在")

    if move_data.collection_id == interface.collection_id:
        linked_cases, linked_execution_items = await _collect_interface_move_links(db, interface_id)
        summary = _build_interface_move_summary(
            interface=interface,
            old_collection_id=interface.collection_id,
            new_collection_id=interface.collection_id,
            linked_cases=linked_cases,
            linked_execution_items=linked_execution_items,
        )
        return success_response(data=summary, message="接口已在目标接口集")

    existing = (await db.execute(
        select(Interface).where(
            Interface.id != interface_id,
            Interface.collection_id == move_data.collection_id,
            Interface.name == interface.name,
            Interface.is_deleted == False,
        )
    )).scalars().first()
    if existing:
        raise UnifiedException(code=400, message="目标接口集下接口名称已存在")

    old_collection_id = interface.collection_id
    interface.collection_id = move_data.collection_id
    linked_cases, linked_execution_items = await _collect_interface_move_links(db, interface_id)
    summary = _build_interface_move_summary(
        interface=interface,
        old_collection_id=old_collection_id,
        new_collection_id=interface.collection_id,
        linked_cases=linked_cases,
        linked_execution_items=linked_execution_items,
    )
    await db.commit()

    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="interface",
        operation="move",
        target_id=interface.id,
        target_name=interface.name,
        description=build_project_audit_description(
            source_project.name,
            f"移动接口：{interface.name} ({old_collection_id} -> {interface.collection_id})",
        ),
    )

    return success_response(data=summary, message="接口移动成功")


@router.post("/{interface_id}/copy")
async def copy_interface(
    interface_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """复制接口"""
    result = await db.execute(select(Interface).where(Interface.id == interface_id, Interface.is_deleted == False))
    interface = result.scalar_one_or_none()

    if not interface:
        raise UnifiedException(code=400, message="接口不存在")
    project = await _ensure_interface_manage_permission(db, interface, current_user)

    # 生成新名称 _copy1, _copy2, ...
    base_name = interface.name
    new_name = f"{base_name}_copy1"
    counter = 1
    while True:
        existing = (await db.execute(
            select(Interface).where(
                Interface.collection_id == interface.collection_id,
                Interface.name == new_name,
                Interface.is_deleted == False
            )
        )).scalars().first()
        if not existing:
            break
        counter += 1
        if counter > 99999999:
            raise UnifiedException(code=400, message="复制数量已达上限")
        new_name = f"{base_name}_copy{counter}"

    new_interface = Interface(
        name=new_name,
        method=interface.method,
        url=interface.url,
        service_key=interface.service_key,
        description=interface.description,
        tags=interface.tags,
        collection_id=interface.collection_id,
        query_params=interface.query_params,
        path_params=interface.path_params,
        body_type=interface.body_type,
        body_content=interface.body_content,
        body_schema_types=interface.body_schema_types or {},
        headers=interface.headers,
        pre_script=interface.pre_script,
        post_script=interface.post_script,
        response_example=interface.response_example,
        workflow_status=INTERFACE_STATUS_PENDING,
        pending_reason=PENDING_REASON_NEW,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(new_interface)
    await db.commit()
    await db.refresh(new_interface)
    new_interface.creator = current_user
    new_interface.modifier = current_user
    await log_user_operation(
        db=db,
        user=current_user,
        module="interface",
        operation="copy",
        target_id=new_interface.id,
        target_name=new_interface.name,
        description=build_project_audit_description(
            project.name,
            f"复制接口：{interface.name} -> {new_interface.name}",
        ),
    )

    return success_response(data=_interface_payload(new_interface, current_user), message="接口复制成功")


@router.delete("/{interface_id}")
async def delete_interface(
    interface_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """删除接口（软删除）"""
    result = await db.execute(select(Interface).where(Interface.id == interface_id, Interface.is_deleted == False))
    interface = result.scalar_one_or_none()

    if not interface:
        raise UnifiedException(code=400, message="接口不存在")
    await _ensure_interface_manage_permission(db, interface, current_user)
    project = await _get_interface_project(db, interface)

    now = beijing_now()
    interface.is_deleted = True
    interface.deleted_at = now
    interface.updated_by = current_user.id

    case_result = await db.execute(
        select(TestCase).where(
            TestCase.interface_id == interface_id,
            TestCase.is_deleted == False,
        )
    )
    cases = case_result.scalars().all()
    case_ids = [tc.id for tc in cases]
    delete_details = _build_interface_delete_details(
        interfaces=[interface],
        cases=cases,
        delete_type="single",
    )
    for tc in cases:
        tc.is_deleted = True
        tc.deleted_at = now
        tc.updated_by = current_user.id

    if case_ids:
        item_result = await db.execute(
            select(ExecutionItem).where(
                ExecutionItem.test_case_id.in_(case_ids),
                ExecutionItem.is_deleted == False,
            )
        )
        for item in item_result.scalars().all():
            item.is_deleted = True
            item.deleted_at = now
    await db.commit()

    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="api_import",
        operation="删除",
        target_id=project.id,
        target_name=project.name,
        description=build_project_audit_description(project.name, delete_details["summary"]),
        details=delete_details,
    )
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="interface",
        operation="delete",
        target_id=interface.id,
        target_name=interface.name,
        description=build_project_audit_description(project.name, f"删除接口：{interface.name}"),
    )

    return success_response(data={"deleted_cases": len(case_ids)}, message="接口删除成功")


class BatchDeleteRequest(BaseModel):
    ids: list[int]


class BatchServiceRequest(BaseModel):
    ids: list[int]
    service_key: str | None = None


class BatchWorkflowStatusRequest(BaseModel):
    ids: list[int]
    workflow_status: str


@router.post("/batch-service")
async def batch_update_interface_service(
    req: BatchServiceRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """批量设置接口所属服务；用例运行时继承接口服务。"""
    if not req.ids:
        raise UnifiedException(code=400, message="请选择要设置的接口")
    result = await db.execute(
        select(Interface).where(Interface.id.in_(req.ids), Interface.is_deleted == False)
    )
    interfaces = list(result.scalars().all())
    project_result = await db.execute(
        select(Interface.id, Project)
        .select_from(Interface)
        .join(InterfaceCollection, InterfaceCollection.id == Interface.collection_id)
        .join(Project, Project.id == InterfaceCollection.project_id)
        .where(Interface.id.in_([interface.id for interface in interfaces]), Project.is_deleted == False)
    )
    project_by_interface_id = {row[0]: row[1] for row in project_result.all()}
    if set(project_by_interface_id) != {interface.id for interface in interfaces}:
        raise UnifiedException(code=400, message="接口所属项目不存在或已删除")
    for iface in interfaces:
        await _ensure_interface_manage_permission(db, iface, current_user)
    for iface in interfaces:
        iface.service_key = req.service_key or None
        iface.updated_by = current_user.id
    await db.commit()

    counts_by_project: dict[int, int] = {}
    for iface in interfaces:
        project = project_by_interface_id[iface.id]
        counts_by_project[project.id] = counts_by_project.get(project.id, 0) + 1
    for project_id, count in counts_by_project.items():
        project = next(item for item in project_by_interface_id.values() if item.id == project_id)
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="interface",
            operation="batch_update_service",
            target_id=project.id,
            target_name=project.name,
            description=build_batch_audit_description(project.name, "批量设置服务", "接口", count),
            details={"count": count, "service_key": req.service_key},
        )
    return success_response(data={"updated": len(interfaces)}, message=f"已更新 {len(interfaces)} 个接口")


@router.post("/batch-workflow-status")
async def batch_update_interface_workflow_status(
    req: BatchWorkflowStatusRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批量标记接口工作状态；只允许待处理和已处理两种状态。"""
    if not req.ids:
        raise UnifiedException(code=400, message="请选择要处理的接口")
    if req.workflow_status not in {INTERFACE_STATUS_PENDING, INTERFACE_STATUS_DONE}:
        raise UnifiedException(code=400, message="接口状态不正确")

    result = await db.execute(
        select(Interface).where(Interface.id.in_(req.ids), Interface.is_deleted == False)
    )
    interfaces = list(result.scalars().all())
    if len(interfaces) != len(set(req.ids)):
        raise UnifiedException(code=400, message="部分接口不存在或已删除，请刷新后重试")
    project_by_id = {}
    project_id_by_interface_id = {}
    for interface in interfaces:
        project = await _ensure_interface_manage_permission(db, interface, current_user)
        project_by_id[project.id] = project
        project_id_by_interface_id[interface.id] = project.id

    for interface in interfaces:
        if req.workflow_status == INTERFACE_STATUS_DONE:
            mark_interface_done(interface)
        else:
            # 已处理接口重新切回待处理时没有新的业务来源，保留已有来源；
            # 空来源只可能来自异常或历史数据，统一按存量数据待确认展示。
            interface.workflow_status = INTERFACE_STATUS_PENDING
            if not interface.pending_reason:
                interface.pending_reason = PENDING_REASON_LEGACY
        interface.updated_by = current_user.id
    await db.commit()
    for project in project_by_id.values():
        project_count = sum(
            1
            for interface in interfaces
            if project_id_by_interface_id.get(interface.id) == project.id
        )
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="interface",
            operation="batch_update_workflow_status",
            target_id=project.id,
            target_name=project.name,
            description=build_batch_audit_description(
                project.name,
                "批量处理接口状态",
                "接口",
                project_count,
            ),
            details={"count": project_count, "workflow_status": req.workflow_status},
        )
    return success_response(
        data={"updated": len(interfaces), "workflow_status": req.workflow_status},
        message=f"已更新 {len(interfaces)} 个接口状态",
    )


def _build_interface_delete_details(
    interfaces: list[Interface],
    cases: list[TestCase],
    delete_type: str,
) -> dict:
    return build_interface_delete_details(interfaces, cases, delete_type)


@router.post("/batch-delete")
async def batch_delete_interfaces(
    req: BatchDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """批量删除接口（软删除），同时软删除关联的用例"""
    if not req.ids:
        raise UnifiedException(code=400, message="请选择要删除的接口")
    now = beijing_now()

    # 软删除接口
    result = await db.execute(
        select(Interface).where(Interface.id.in_(req.ids), Interface.is_deleted == False)
    )
    interfaces = list(result.scalars().all())
    if not interfaces:
        return success_response(
            data={"deleted_interfaces": 0, "deleted_cases": 0},
            message="未找到可删除的接口",
        )

    interface_ids = [interface.id for interface in interfaces]
    project_result = await db.execute(
        select(Interface.id, Project)
        .select_from(Interface)
        .join(InterfaceCollection, InterfaceCollection.id == Interface.collection_id)
        .join(Project, Project.id == InterfaceCollection.project_id)
        .where(
            Interface.id.in_(interface_ids),
            InterfaceCollection.is_deleted == False,
            Project.is_deleted == False,
        )
    )
    project_by_interface_id = {row[0]: row[1] for row in project_result.all()}
    if set(project_by_interface_id) != set(interface_ids):
        raise UnifiedException(code=400, message="接口所属项目不存在或已删除")
    projects = list(project_by_interface_id.values())
    if len({project.id for project in projects}) != 1:
        raise UnifiedException(code=400, message="批量删除接口必须属于同一项目")
    project = projects[0]

    for iface in interfaces:
        await _ensure_interface_manage_permission(db, iface, current_user)
    for iface in interfaces:
        iface.is_deleted = True
        iface.deleted_at = now
        iface.updated_by = current_user.id

    # 级联软删除关联用例
    case_r = await db.execute(
        select(TestCase).where(
            TestCase.interface_id.in_([interface.id for interface in interfaces]),
            TestCase.is_deleted == False,
        )
    )
    cases = list(case_r.scalars().all())
    case_count = len(cases)
    delete_details = _build_interface_delete_details(
        interfaces=interfaces,
        cases=cases,
        delete_type="batch",
    )
    case_ids = [tc.id for tc in cases]
    for tc in cases:
        tc.is_deleted = True
        tc.deleted_at = now
        tc.updated_by = current_user.id

    if case_count:
        item_r = await db.execute(
            select(ExecutionItem).where(
                ExecutionItem.test_case_id.in_(case_ids),
                ExecutionItem.is_deleted == False
            )
        )
        execution_items = list(item_r.scalars().all())
        execution_item_count = len(execution_items)
        for item in execution_items:
            item.is_deleted = True
            item.deleted_at = now
    else:
        execution_item_count = 0

    await db.commit()

    delete_details["execution_item_count"] = execution_item_count
    delete_details["summary"] = build_batch_audit_description(
        project.name,
        "删除",
        "接口",
        len(interfaces),
        {"用例": case_count, "执行项": execution_item_count},
    )
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="api_import",
        operation="删除",
        target_id=project.id,
        target_name=project.name,
        description=delete_details["summary"],
        details=delete_details,
    )

    deleted_interfaces = len(interfaces)
    return success_response(
        data={"deleted_interfaces": deleted_interfaces, "deleted_cases": case_count},
        message=f"已删除 {deleted_interfaces} 个接口及其 {case_count} 个关联用例",
    )
