"""
Interface collection management endpoints (接口集管理)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import List
from db.session import get_db
from models.models import InterfaceCollection, Interface, Project, User, TestCase, ExecutionItem
from core.security import get_current_active_user
from core.response import success_response, UnifiedException
from core.timezone import beijing_now
from pydantic import BaseModel
from datetime import datetime, timezone
from utils.audit_logger import (
    build_batch_audit_description,
    build_interface_delete_details,
    build_project_audit_description,
    merge_interface_delete_details,
    log_operation,
    log_user_operation,
)
from core.permissions import ensure_project_access, ensure_project_asset_manage
from services.collection_tree import build_collection_tree, get_descendant_collection_ids, would_create_collection_cycle
from services.api_test_workflow import INTERFACE_STATUS_DONE

router = APIRouter()


async def _ensure_project_manage_permission(db: AsyncSession, project_id: int, current_user: User) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    return project


async def _ensure_collection_parent_is_valid(
    db: AsyncSession,
    collection_id: int,
    parent_id: int | None,
    project_id: int,
) -> None:
    if parent_id is None:
        return
    if parent_id == collection_id:
        raise UnifiedException(code=400, message="父级接口集不能是当前接口集或其子目录")

    result = await db.execute(
        select(InterfaceCollection.id, InterfaceCollection.parent_id).where(
            InterfaceCollection.project_id == project_id,
            InterfaceCollection.is_deleted == False,
        )
    )
    parent_map = {row[0]: row[1] for row in result.all()}
    if would_create_collection_cycle(collection_id, parent_id, parent_map):
        raise UnifiedException(code=400, message="父级接口集不能是当前接口集或其子目录")


async def _soft_delete_interfaces_cases_and_execution_items(
    db: AsyncSession,
    collection_ids: list[int],
    now: datetime,
) -> tuple[int, int, int]:
    """Soft-delete interfaces in collections and their linked cases/execution items."""
    if not collection_ids:
        return 0, 0, 0

    ifaces_result = await db.execute(
        select(Interface).where(
            Interface.collection_id.in_(collection_ids),
            Interface.is_deleted == False,
        )
    )
    interfaces = ifaces_result.scalars().all()
    iface_ids = [iface.id for iface in interfaces]

    for iface in interfaces:
        iface.is_deleted = True
        iface.deleted_at = now

    test_cases = []
    if iface_ids:
        tc_result = await db.execute(
            select(TestCase).where(
                TestCase.interface_id.in_(iface_ids),
                TestCase.is_deleted == False,
            )
        )
        test_cases = tc_result.scalars().all()

    tc_ids = [tc.id for tc in test_cases]
    for tc in test_cases:
        tc.is_deleted = True
        tc.deleted_at = now

    execution_items = []
    if tc_ids:
        ei_result = await db.execute(
            select(ExecutionItem).where(
                ExecutionItem.test_case_id.in_(tc_ids),
                ExecutionItem.is_deleted == False,
            )
        )
        execution_items = ei_result.scalars().all()

    for ei in execution_items:
        ei.is_deleted = True
        ei.deleted_at = now

    return len(interfaces), len(test_cases), len(execution_items)


async def _build_collection_delete_details(
    db: AsyncSession,
    collection_ids: list[int],
    delete_type: str,
) -> dict:
    """收集接口集级联删除前的接口和用例轻量快照。"""
    ifaces_result = await db.execute(
        select(Interface).where(
            Interface.collection_id.in_(collection_ids),
            Interface.is_deleted == False,
        )
    )
    interfaces = list(ifaces_result.scalars().all())
    if not interfaces:
        return build_interface_delete_details([], [], delete_type)

    case_result = await db.execute(
        select(TestCase).where(
            TestCase.interface_id.in_([interface.id for interface in interfaces]),
            TestCase.is_deleted == False,
        )
    )
    cases = list(case_result.scalars().all())
    return build_interface_delete_details(interfaces, cases, delete_type)


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None
    project_id: int
    parent_id: int | None = None


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_id: int | None = None


class CollectionResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    project_id: int
    parent_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class CollectionTreeNode(BaseModel):
    id: int
    name: str
    description: str | None = None
    project_id: int
    parent_id: int | None = None
    interface_count: int = 0
    pending_interface_count: int = 0
    done_interface_count: int = 0
    interface_status: str = "empty"
    children: list["CollectionTreeNode"] = []

    class Config:
        from_attributes = True


@router.get("/tree/{project_id}")
async def get_collection_tree(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取项目的接口集树形结构"""
    result = await db.execute(
        select(InterfaceCollection).where(InterfaceCollection.project_id == project_id, InterfaceCollection.is_deleted == False).order_by(InterfaceCollection.sort_order, InterfaceCollection.id)
    )
    project_result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    collections = result.scalars().all()

    # 统计每个接口集下的接口数量和状态（一次 GROUP BY 查询）
    interface_counts = {}
    if collections:
        pending_count = case(
            (Interface.workflow_status == INTERFACE_STATUS_DONE, 0),
            else_=1,
        )
        done_count = case(
            (Interface.workflow_status == INTERFACE_STATUS_DONE, 1),
            else_=0,
        )
        count_result = await db.execute(
            select(
                Interface.collection_id,
                func.count(Interface.id),
                func.sum(pending_count),
                func.sum(done_count),
            )
            .where(Interface.collection_id.in_([c.id for c in collections]), Interface.is_deleted == False)
            .group_by(Interface.collection_id)
        )
        interface_counts = {
            int(collection_id): {
                "total_count": int(total_count or 0),
                "pending_count": int(pending_count_value or 0),
                "done_count": int(done_count_value or 0),
            }
            for collection_id, total_count, pending_count_value, done_count_value in count_result.all()
        }

    return success_response(data=build_collection_tree(collections, interface_counts))


@router.get("/")
async def list_collections(
    project_id: int,
    parent_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取接口集列表"""
    project_result = await db.execute(select(Project).where(Project.id == project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    query = select(InterfaceCollection).where(InterfaceCollection.project_id == project_id, InterfaceCollection.is_deleted == False)
    if parent_id is not None:
        query = query.where(InterfaceCollection.parent_id == parent_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return success_response(data=result.scalars().all())


@router.post("/")
async def create_collection(
    col_data: CollectionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """创建接口集"""
    project = await _ensure_project_manage_permission(db, col_data.project_id, current_user)

    if col_data.parent_id:
        result = await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id == col_data.parent_id,
                InterfaceCollection.project_id == col_data.project_id,
                InterfaceCollection.is_deleted == False,
            )
        )
        if not result.scalar_one_or_none():
            raise UnifiedException(code=400, message="父级接口集不存在")

    # 检查同层级下名称是否重复
    from sqlalchemy import or_
    parent_cond = InterfaceCollection.parent_id == col_data.parent_id if col_data.parent_id else InterfaceCollection.parent_id.is_(None)
    existing = (await db.execute(
        select(InterfaceCollection).where(
            InterfaceCollection.project_id == col_data.project_id,
            parent_cond,
            InterfaceCollection.name == col_data.name,
            InterfaceCollection.is_deleted == False
        )
    )).scalars().first()
    if existing:
        raise UnifiedException(code=400, message="该层级下接口集名称已存在")

    db_col = InterfaceCollection(
        name=col_data.name,
        description=col_data.description,
        project_id=col_data.project_id,
        parent_id=col_data.parent_id,
    )
    db.add(db_col)
    await db.commit()
    await db.refresh(db_col)

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="interface",
        operation="create",
        target_id=db_col.id,
        target_name=db_col.name,
        description=build_project_audit_description(project.name, f"创建接口集：{db_col.name}"),
    )

    return success_response(data=db_col, message="接口集创建成功")


class ReorderItem(BaseModel):
    id: int
    parent_id: int | None = None
    sort_order: int = 0


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


@router.put("/reorder")
async def reorder_collections(
    req: ReorderRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """拖拽排序接口集"""
    resolved_items = []
    projects_by_id = {}
    for item in req.items:
        col = (await db.execute(
            select(InterfaceCollection).where(InterfaceCollection.id == item.id)
        )).scalars().first()
        if col:
            projects_by_id[col.project_id] = await _ensure_project_manage_permission(db, col.project_id, current_user)
            if item.parent_id is not None:
                parent_result = await db.execute(
                    select(InterfaceCollection).where(
                        InterfaceCollection.id == item.parent_id,
                        InterfaceCollection.project_id == col.project_id,
                        InterfaceCollection.is_deleted == False,
                    )
                )
                if not parent_result.scalar_one_or_none():
                    raise UnifiedException(code=400, message="父级接口集不存在或不属于当前项目")
            resolved_items.append((item, col))

    # 先按本次请求构造预期父级关系，再统一校验，避免一次拖拽提交多个节点时互相形成循环。
    prospective_maps = {}
    for _item, col in resolved_items:
        if col.project_id not in prospective_maps:
            result = await db.execute(
                select(InterfaceCollection.id, InterfaceCollection.parent_id).where(
                    InterfaceCollection.project_id == col.project_id,
                    InterfaceCollection.is_deleted == False,
                )
            )
            prospective_maps[col.project_id] = {row[0]: row[1] for row in result.all()}
    for item, col in resolved_items:
        prospective_maps[col.project_id][col.id] = item.parent_id
    for item, col in resolved_items:
        if would_create_collection_cycle(col.id, item.parent_id, prospective_maps[col.project_id]):
            raise UnifiedException(code=400, message="父级接口集不能是当前接口集或其子目录")

    # 拖拽换父级同样要守住「同层级不重名」，否则会绕过新建与重命名两处已有校验
    for project_id, parent_map in prospective_maps.items():
        rows = (await db.execute(
            select(InterfaceCollection.id, InterfaceCollection.name).where(
                InterfaceCollection.project_id == project_id,
                InterfaceCollection.is_deleted == False,
            )
        )).all()
        name_by_id = {row[0]: str(row[1] or "").strip() for row in rows}
        for item, col in resolved_items:
            if col.project_id != project_id:
                continue
            moved_name = name_by_id.get(col.id, "")
            for other_id, other_parent in parent_map.items():
                if other_id == col.id or other_parent != item.parent_id:
                    continue
                if name_by_id.get(other_id, "") == moved_name:
                    raise UnifiedException(code=400, message="该层级下接口集名称已存在")

    for item, col in resolved_items:
        col.parent_id = item.parent_id
        col.sort_order = item.sort_order
    await db.commit()
    counts_by_project = {}
    for _, col in resolved_items:
        counts_by_project[col.project_id] = counts_by_project.get(col.project_id, 0) + 1
    for project_id, count in counts_by_project.items():
        project = projects_by_id[project_id]
        await log_user_operation(
            db=db,
            user=current_user,
            module="interface",
            operation="排序",
            target_id=project.id,
            target_name=project.name,
            description=build_project_audit_description(project.name, f"调整{count}个接口集排序"),
            details={"count": count},
        )
    return success_response(message="排序已保存")


@router.get("/{col_id}")
async def get_collection(
    col_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取接口集详情"""
    result = await db.execute(select(InterfaceCollection).where(InterfaceCollection.id == col_id, InterfaceCollection.is_deleted == False))
    col = result.scalar_one_or_none()
    if not col:
        raise UnifiedException(code=400, message="接口集不存在")
    project_result = await db.execute(select(Project).where(Project.id == col.project_id, Project.is_deleted == False))
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    return success_response(data=col)


@router.put("/{col_id}")
async def update_collection(
    col_id: int,
    col_data: CollectionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新接口集"""
    result = await db.execute(select(InterfaceCollection).where(InterfaceCollection.id == col_id, InterfaceCollection.is_deleted == False))
    col = result.scalar_one_or_none()
    if not col:
        raise UnifiedException(code=400, message="接口集不存在")
    if col_data.parent_id is not None:
        parent_result = await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id == col_data.parent_id,
                InterfaceCollection.project_id == col.project_id,
                InterfaceCollection.is_deleted == False,
            )
        )
        if not parent_result.scalar_one_or_none():
            raise UnifiedException(code=400, message="父级接口集不存在或不属于当前项目")
        await _ensure_collection_parent_is_valid(db, col_id, col_data.parent_id, col.project_id)
    project = await _ensure_project_manage_permission(db, col.project_id, current_user)

    # 如果修改了名称或父级，检查同层级是否重复
    if col_data.name or col_data.parent_id is not None:
        new_name = col_data.name if col_data.name else col.name
        new_parent = col_data.parent_id if col_data.parent_id is not None else col.parent_id
        from sqlalchemy import or_
        parent_cond = InterfaceCollection.parent_id == new_parent if new_parent else InterfaceCollection.parent_id.is_(None)
        existing = (await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id != col_id,
                InterfaceCollection.project_id == col.project_id,
                parent_cond,
                InterfaceCollection.name == new_name,
                InterfaceCollection.is_deleted == False
            )
        )).scalars().first()
        if existing:
            raise UnifiedException(code=400, message="该层级下接口集名称已存在")

    update_data = col_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(col, field, value)

    await db.commit()
    await db.refresh(col)

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="interface",
        operation="update",
        target_id=col.id,
        target_name=col.name,
        description=build_project_audit_description(project.name, f"更新接口集：{col.name}"),
    )

    return success_response(data=col, message="接口集更新成功")


@router.get("/{col_id}/delete-preview")
async def preview_delete_collection(
    col_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """预览删除接口集将影响的数据"""
    result = await db.execute(select(InterfaceCollection).where(InterfaceCollection.id == col_id, InterfaceCollection.is_deleted == False))
    col = result.scalar_one_or_none()
    if not col:
        raise UnifiedException(code=400, message="接口集不存在")
    await _ensure_project_manage_permission(db, col.project_id, current_user)

    collection_ids = await get_descendant_collection_ids(db, [col_id], project_id=col.project_id)
    child_ids = [cid for cid in collection_ids if cid != col_id]

    # 接口
    ifaces_result = await db.execute(select(Interface).where(Interface.collection_id.in_(collection_ids), Interface.is_deleted == False))
    interfaces = ifaces_result.scalars().all()

    # 关联用例
    iface_ids = [iface.id for iface in interfaces]
    linked_tcs = []
    if iface_ids:
        tc_result = await db.execute(
            select(TestCase).where(TestCase.interface_id.in_(iface_ids), TestCase.is_deleted == False)
        )
        linked_tcs = tc_result.scalars().all()

    # 执行项
    tc_ids = [tc.id for tc in linked_tcs]
    linked_eis = []
    if tc_ids:
        ei_result = await db.execute(
            select(ExecutionItem).where(ExecutionItem.test_case_id.in_(tc_ids), ExecutionItem.is_deleted == False)
        )
        linked_eis = ei_result.scalars().all()

    return success_response(data={
        "children_count": len(child_ids),
        "interfaces_count": len(interfaces),
        "test_cases_count": len(linked_tcs),
        "execution_items_count": len(linked_eis),
    })


@router.delete("/{col_id}")
async def delete_collection(
    col_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """删除接口集（级联软删除：接口集 → 接口 → 用例 → 步骤 → 执行项）"""
    result = await db.execute(select(InterfaceCollection).where(InterfaceCollection.id == col_id, InterfaceCollection.is_deleted == False))
    col = result.scalar_one_or_none()
    if not col:
        raise UnifiedException(code=400, message="接口集不存在")
    project = await _ensure_project_manage_permission(db, col.project_id, current_user)
    project_id = project.id
    project_name = project.name
    collection_id = col.id
    collection_name = col.name

    now = beijing_now()

    collection_ids = await get_descendant_collection_ids(db, [col_id], project_id=col.project_id)
    delete_details = await _build_collection_delete_details(db, collection_ids, delete_type="collection")

    # 1. 软删除子目录
    children_result = await db.execute(
        select(InterfaceCollection).where(
            InterfaceCollection.id.in_([cid for cid in collection_ids if cid != col_id]),
            InterfaceCollection.is_deleted == False,
        )
    )
    for child in children_result.scalars().all():
        child.is_deleted = True
        child.deleted_at = now

    # 2. 级联软删除接口、用例、执行项
    await _soft_delete_interfaces_cases_and_execution_items(db, collection_ids, now)

    # 6. 软删除接口集本身
    col.is_deleted = True
    col.deleted_at = now

    await db.commit()

    if delete_details["interface_count"]:
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="api_import",
            operation="删除",
            target_id=project_id,
            target_name=project_name,
            description=build_project_audit_description(project_name, delete_details["summary"]),
            details=delete_details,
        )

    # 记录审计日志
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="interface",
        operation="delete",
        target_id=collection_id,
        target_name=collection_name,
        description=build_project_audit_description(project_name, f"删除接口集：{collection_name}"),
    )

    return success_response(message="接口集删除成功")


class BatchDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/batch-delete")
async def batch_delete_collections(
    req: BatchDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """批量删除接口集（级联软删除）"""
    if not req.ids:
        raise UnifiedException(code=400, message="请选择要删除的接口集")

    now = beijing_now()
    deleted = 0
    delete_audits = {}
    collections = []

    # 先完整校验所有目标，避免前面的接口集已删除、后面的接口集才触发权限错误。
    for col_id in dict.fromkeys(req.ids):
        result = await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id == col_id,
                InterfaceCollection.is_deleted == False
            )
        )
        col = result.scalar_one_or_none()
        if not col:
            continue
        await _ensure_project_manage_permission(db, col.project_id, current_user)
        collections.append(col)

    for col in collections:
        col_id = col.id
        project = await _ensure_project_manage_permission(db, col.project_id, current_user)
        collection_ids = await get_descendant_collection_ids(db, [col_id], project_id=col.project_id)
        delete_details = await _build_collection_delete_details(db, collection_ids, delete_type="collection_batch")

        # 软删除子目录
        children_result = await db.execute(
            select(InterfaceCollection).where(
                InterfaceCollection.id.in_([cid for cid in collection_ids if cid != col_id]),
                InterfaceCollection.is_deleted == False,
            )
        )
        for child in children_result.scalars().all():
            child.is_deleted = True
            child.deleted_at = now

        # 级联软删除接口、用例、执行项
        _, _, execution_item_count = await _soft_delete_interfaces_cases_and_execution_items(
            db,
            collection_ids,
            now,
        )

        col.is_deleted = True
        col.deleted_at = now
        deleted += 1
        audit = delete_audits.setdefault(
            project.id,
            {
                "project_name": project.name,
                "details": [],
                "collection_ids": set(),
                "execution_item_count": 0,
            },
        )
        audit["details"].append(delete_details)
        audit["collection_ids"].update(collection_ids)
        audit["execution_item_count"] += execution_item_count

    await db.commit()

    for project_id, audit in delete_audits.items():
        delete_details = merge_interface_delete_details(
            audit["details"],
            delete_type="collection_batch",
        )
        delete_details["collection_count"] = len(audit["collection_ids"])
        delete_details["execution_item_count"] = audit["execution_item_count"]
        delete_details["summary"] = build_batch_audit_description(
            audit["project_name"],
            "删除",
            "接口集",
            len(audit["collection_ids"]),
            {
                "接口": delete_details["interface_count"],
                "用例": delete_details["case_count"],
                "执行项": delete_details["execution_item_count"],
            },
        )
        await log_operation(
            db=db,
            user_id=current_user.id,
            user_name=current_user.real_name,
            module="api_import",
            operation="删除",
            target_id=project_id,
            target_name=audit["project_name"],
            description=delete_details["summary"],
            details=delete_details,
        )

    return success_response(data={"deleted": deleted}, message=f"成功删除 {deleted} 个接口集")
