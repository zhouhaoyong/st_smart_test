"""参数项列表、单项 CRUD（用于详情页内联编辑）与引用查询。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from db.session import get_db
from models.models import ParameterSet, ParameterItem, User
from core.security import get_current_active_user
from core.response import mask_sensitive_data, success_response, UnifiedException
from core.timezone import beijing_now
from utils.audit_logger import build_batch_audit_description, build_project_audit_description, log_user_operation

from ._shared import (
    _ensure_parameter_set_manage_permission,
    _ensure_project_access_permission,
    _active_items_for_parameter_set,
    _display_name_conflicts,
    _key_conflicts,
    _ensure_unique_display_names,
    _ensure_unique_keys,
    ItemCreate,
    ItemUpdate,
    ParameterItemSchema,
)
from services.parameter_reference_service import (
    _find_parameter_item_references,
    _deparameterize_parameter_references,
    _deparameterize_parameter_references_bulk,
)

router = APIRouter()


def _matches_parameter_item_search(item, name: str | None = None, key: str | None = None, value: str | None = None) -> bool:
    """用于测试和非 SQL 场景的参数项筛选语义：多个条件同时满足。"""
    fields = {
        "name": str(getattr(item, "display_name", "") or "").lower(),
        "key": str(getattr(item, "key", "") or "").lower(),
        "value": str(getattr(item, "value", "") or "").lower(),
    }
    filters = {"name": name, "key": key, "value": value}
    return all(
        not str(term or "").strip() or str(term).strip().lower() in fields[field]
        for field, term in filters.items()
    )


def _parameter_item_data(item, current_user: User) -> dict:
    item_data = {
        "id": item.id,
        "display_name": item.display_name,
        "key": item.key,
        "value": item.value,
        "type": item.type,
        "type_source": item.type_source or "manual",
        "description": item.description,
        "sort_order": item.sort_order,
        "created_at": str(item.created_at) if item.created_at else None,
    }
    if not getattr(current_user, "is_manager", False) and not getattr(current_user, "is_superuser", False):
        item_data = mask_sensitive_data(item_data)
    return item_data


def _parameter_item_conditions(ps_id: int, name: str | None = None, key: str | None = None, value: str | None = None):
    conditions = [
        ParameterItem.parameter_set_id == ps_id,
        ParameterItem.is_deleted == False,
    ]
    for column, term in (
        (ParameterItem.display_name, name),
        (ParameterItem.key, key),
        (ParameterItem.value, value),
    ):
        normalized = str(term or "").strip()
        if normalized:
            conditions.append(column.ilike(f"%{normalized}%"))
    return conditions


class BatchDeleteItemsRequest(BaseModel):
    """批量删除当前参数集中的参数项。"""
    ids: list[int] = Field(default_factory=list)
    delete_all_in_scope: bool = False
    name: str | None = None
    key: str | None = None
    value: str | None = None


class BatchCreateItemsRequest(BaseModel):
    """批量新增当前参数集中的参数项。"""
    items: list[ParameterItemSchema] = Field(default_factory=list)


@router.get("/{ps_id}/items")
async def list_parameter_items(
    ps_id: int,
    name: str | None = Query(None, description="参数名称模糊查询"),
    key: str | None = Query(None, description="Key 模糊查询"),
    value: str | None = Query(None, description="参数值模糊查询"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """按当前参数集查询参数项，默认按创建时间倒序返回稳定分页结果。"""
    result = await db.execute(
        select(ParameterSet).where(ParameterSet.id == ps_id, ParameterSet.is_deleted == False)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise UnifiedException(code=400, message="参数集不存在")
    await _ensure_project_access_permission(db, ps.project_id, current_user)

    conditions = _parameter_item_conditions(ps_id, name, key, value)

    count_result = await db.execute(
        select(func.count(ParameterItem.id)).where(*conditions)
    )
    total = count_result.scalar() or 0
    items_result = await db.execute(
        select(ParameterItem)
        .where(*conditions)
        .order_by(ParameterItem.created_at.desc(), ParameterItem.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = [_parameter_item_data(item, current_user) for item in items_result.scalars().all()]
    return success_response(data={
        "items": items,
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
    })


@router.post("/{ps_id}/items")
async def add_item(
    ps_id: int,
    data: ItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ParameterSet).where(ParameterSet.id == ps_id, ParameterSet.is_deleted == False)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise UnifiedException(code=400, message="参数集不存在")
    project = await _ensure_parameter_set_manage_permission(db, ps, current_user)

    active_items = await _active_items_for_parameter_set(db, ps_id)
    if _display_name_conflicts(active_items, data.display_name):
        raise UnifiedException(code=400, message=f"参数名称「{data.display_name}」已存在")
    if _key_conflicts(active_items, data.key):
        raise UnifiedException(code=400, message=f"Key「{data.key}」已存在")

    item = ParameterItem(
        parameter_set_id=ps_id, display_name=data.display_name, key=data.key, value=data.value,
        type=data.type, type_source=data.type_source, description=data.description, sort_order=data.sort_order
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    await log_user_operation(
        db=db,
        user=current_user,
        module="parameter_set",
        operation="新增",
        target_id=item.id,
        target_name=item.display_name or item.key,
        description=build_project_audit_description(
            project.name,
            f"新增参数项：{item.display_name or item.key}",
        ),
    )

    return success_response(data={"id": item.id, "key": item.key}, message="参数项添加成功")


@router.post("/{ps_id}/items/batch")
async def batch_add_items(
    ps_id: int,
    data: BatchCreateItemsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批量新增参数项，并按一次业务操作记录汇总审计。"""
    result = await db.execute(
        select(ParameterSet).where(ParameterSet.id == ps_id, ParameterSet.is_deleted == False)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise UnifiedException(code=400, message="参数集不存在")
    project = await _ensure_parameter_set_manage_permission(db, ps, current_user)
    if not data.items:
        return success_response(data={"created_count": 0}, message="未选择要新增的参数项")

    active_items = await _active_items_for_parameter_set(db, ps_id)
    _ensure_unique_display_names(data.items)
    _ensure_unique_keys(data.items)
    for item_data in data.items:
        if _display_name_conflicts(active_items, item_data.display_name):
            raise UnifiedException(code=400, message=f"参数名称「{item_data.display_name}」已存在")
        if _key_conflicts(active_items, item_data.key):
            raise UnifiedException(code=400, message=f"Key「{item_data.key}」已存在")

    items = [
        ParameterItem(
            parameter_set_id=ps_id,
            display_name=item_data.display_name,
            key=item_data.key,
            value=item_data.value,
            type=item_data.type,
            type_source=item_data.type_source,
            description=item_data.description,
            sort_order=item_data.sort_order,
        )
        for item_data in data.items
    ]
    db.add_all(items)
    await db.commit()
    created_count = len(items)
    await log_user_operation(
        db=db,
        user=current_user,
        module="parameter_set",
        operation="批量新增",
        target_id=ps_id,
        target_name=ps.name,
        description=build_batch_audit_description(
            project.name,
            "新增",
            "参数项",
            created_count,
        ),
        details={"parameter_set_count": 1, "parameter_item_count": created_count},
    )
    return success_response(
        data={"created_count": created_count},
        message=f"已加入 {created_count} 个参数项",
    )


@router.put("/{ps_id}/items/{item_id}")
async def update_item(
    ps_id: int,
    item_id: int,
    data: ItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ParameterItem, ParameterSet).join(ParameterSet, ParameterSet.id == ParameterItem.parameter_set_id).where(
            ParameterItem.id == item_id,
            ParameterItem.parameter_set_id == ps_id,
            ParameterItem.is_deleted == False,
            ParameterSet.is_deleted == False,
        )
    )
    row = result.first()
    if not row:
        raise UnifiedException(code=400, message="参数项不存在")

    item, _ps = row
    project = await _ensure_parameter_set_manage_permission(db, _ps, current_user)
    if data.display_name is not None or data.key is not None:
        active_items = await _active_items_for_parameter_set(db, ps_id)
    if data.display_name is not None:
        if _display_name_conflicts(active_items, data.display_name, current_item_id=item_id):
            raise UnifiedException(code=400, message=f"参数名称「{data.display_name}」已存在")
    if data.key is not None and _key_conflicts(active_items, data.key, current_item_id=item_id):
        raise UnifiedException(code=400, message=f"Key「{data.key}」已存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="parameter_set",
        operation="更新",
        target_id=item.id,
        target_name=item.display_name or item.key,
        description=build_project_audit_description(
            project.name,
            f"更新参数项：{item.display_name or item.key}",
        ),
        details={"updated_fields": list(update_data.keys())},
    )

    return success_response(message="参数项更新成功")


@router.get("/{ps_id}/items/{item_id}/references")
async def get_item_references(
    ps_id: int,
    item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ParameterItem, ParameterSet).join(ParameterSet, ParameterSet.id == ParameterItem.parameter_set_id).where(
            ParameterItem.id == item_id,
            ParameterItem.parameter_set_id == ps_id,
            ParameterItem.is_deleted == False,
            ParameterSet.is_deleted == False,
        )
    )
    row = result.first()
    if not row:
        raise UnifiedException(code=400, message="参数项不存在")

    item, ps = row
    await _ensure_project_access_permission(db, ps.project_id, current_user)
    refs = await _find_parameter_item_references(db, ps.project_id, item.key)
    return success_response(data={"items": refs, "total": len(refs)})


@router.delete("/{ps_id}/items/{item_id}")
async def delete_item(
    ps_id: int,
    item_id: int,
    force: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ParameterItem, ParameterSet).join(ParameterSet, ParameterSet.id == ParameterItem.parameter_set_id).where(
            ParameterItem.id == item_id,
            ParameterItem.parameter_set_id == ps_id,
            ParameterItem.is_deleted == False,
            ParameterSet.is_deleted == False,
        )
    )
    row = result.first()
    if not row:
        raise UnifiedException(code=400, message="参数项不存在")

    item, ps = row
    project = await _ensure_parameter_set_manage_permission(db, ps, current_user)
    refs = await _find_parameter_item_references(db, ps.project_id, item.key)
    if refs and not force:
        return success_response(
            data={"requires_confirm": True, "items": refs, "total": len(refs)},
            message="参数正在被引用，请确认后再删除"
        )

    deparameterized_count = 0
    if refs and force:
        deparameterized_count = await _deparameterize_parameter_references(
            db, ps.project_id, item.key, item.value, item.type
        )

    item.is_deleted = True
    item.deleted_at = beijing_now()
    item_name = item.display_name or item.key
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="parameter_set",
        operation="删除",
        target_id=item_id,
        target_name=item_name,
        description=build_project_audit_description(project.name, f"删除参数项：{item_name}"),
        details={"deparameterized_count": deparameterized_count},
    )

    if deparameterized_count:
        return success_response(
            data={"deparameterized_count": deparameterized_count},
            message=f"参数项删除成功，已去参数化 {deparameterized_count} 处"
        )
    return success_response(message="参数项删除成功")


@router.post("/{ps_id}/items/batch-delete")
async def batch_delete_items(
    ps_id: int,
    data: BatchDeleteItemsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批量软删除参数项；全部删除只作用于当前参数集和当前筛选条件。"""
    result = await db.execute(
        select(ParameterSet).where(ParameterSet.id == ps_id, ParameterSet.is_deleted == False)
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise UnifiedException(code=400, message="参数集不存在")
    project = await _ensure_parameter_set_manage_permission(db, ps, current_user)

    conditions = _parameter_item_conditions(ps_id)
    if data.delete_all_in_scope:
        conditions = _parameter_item_conditions(ps_id, data.name, data.key, data.value)
    else:
        ids = list(dict.fromkeys(data.ids or []))
        if not ids:
            return success_response(data={"deleted_count": 0, "deparameterized_count": 0}, message="未选择参数项")
        conditions.append(ParameterItem.id.in_(ids))

    items_result = await db.execute(
        select(ParameterItem)
        .where(*conditions)
        .order_by(ParameterItem.sort_order.asc(), ParameterItem.id.asc())
    )
    target_items = items_result.scalars().all()
    if not target_items:
        return success_response(
            data={"deleted_count": 0, "deparameterized_count": 0},
            message="当前条件下没有可删除的参数项",
        )

    replacements = {
        target.key: (target.value, target.type)
        for target in target_items
    }
    deparameterized_count = await _deparameterize_parameter_references_bulk(
        db, ps.project_id, replacements
    )
    for target in target_items:
        target.is_deleted = True
        target.deleted_at = beijing_now()

    deleted_count = len(target_items)
    await db.commit()
    await log_user_operation(
        db=db,
        user=current_user,
        module="parameter_set",
        operation="批量删除",
        target_id=ps_id,
        target_name=ps.name,
        description=build_batch_audit_description(
            project.name,
            "删除",
            "参数项",
            deleted_count,
            {"引用": deparameterized_count},
        ),
        details={
            "deleted_count": deleted_count,
            "deparameterized_count": deparameterized_count,
            "delete_all_in_scope": data.delete_all_in_scope,
        },
    )
    return success_response(
        data={"deleted_count": deleted_count, "deparameterized_count": deparameterized_count},
        message=f"已删除 {deleted_count} 个参数项" + (f"，恢复 {deparameterized_count} 处引用" if deparameterized_count else ""),
    )
