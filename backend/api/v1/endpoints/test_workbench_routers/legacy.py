"""遗留项接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from models.models import TWLegacyItem, User
from schemas.test_workbench import TWLegacyCreate, TWLegacyUpdate
from services.test_workbench_service import ensure_manage_workbench_record, get_project, get_version, to_dict
from services.test_workbench_audit import snapshot_workbench_record, soft_delete_workbench_record

from ._shared import (
    _audit_workbench_mutation,
    _validate_bug_relation,
    _validate_merged_requirement_relation,
    _validate_planned_version,
    _validate_requirement_relation,
    _validate_test_case_relation,
)

router = APIRouter()


@router.post("/legacy-items")
async def create_legacy_item(data: TWLegacyCreate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    version = await get_version(db, data.version_id, current_user)
    await get_project(db, version.project_id, current_user)
    await _validate_requirement_relation(db, current_user, data.requirement_id, version)
    await _validate_merged_requirement_relation(db, current_user, data.merged_requirement_id, version)
    await _validate_test_case_relation(db, current_user, data.test_case_id, version)
    await _validate_bug_relation(db, data.bug_id, version)
    await _validate_planned_version(db, data.planned_version_id, version)
    item_data = data.model_dump()
    item_data["project_id"] = version.project_id
    item_data["system_id"] = version.system_id
    item = TWLegacyItem(**item_data, created_by=current_user.id, updated_by=current_user.id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    await _audit_workbench_mutation(db, current_user, operation="创建", asset_name="遗留项", record=item)
    return success_response(to_dict(item), message="遗留项保存成功")


@router.put("/legacy-items/{item_id}")
async def update_legacy_item(item_id: int, data: TWLegacyUpdate, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(TWLegacyItem).where(TWLegacyItem.id == item_id, TWLegacyItem.is_deleted == False))).scalar_one_or_none()
    if not item:
        raise UnifiedException(code=400, message="遗留项不存在")
    await ensure_manage_workbench_record(db, current_user, item)
    version = await get_version(db, item.version_id, current_user)
    before = snapshot_workbench_record(item)
    payload = data.model_dump(exclude_unset=True)
    if "requirement_id" in payload:
        await _validate_requirement_relation(db, current_user, payload["requirement_id"], version)
    if "merged_requirement_id" in payload:
        await _validate_merged_requirement_relation(db, current_user, payload["merged_requirement_id"], version)
    if "test_case_id" in payload:
        await _validate_test_case_relation(db, current_user, payload["test_case_id"], version)
    if "bug_id" in payload:
        await _validate_bug_relation(db, payload["bug_id"], version)
    if "planned_version_id" in payload:
        await _validate_planned_version(db, payload["planned_version_id"], version)
    for field, value in payload.items():
        setattr(item, field, value)
    item.updated_by = current_user.id
    await db.commit()
    await db.refresh(item)
    await _audit_workbench_mutation(db, current_user, operation="编辑", asset_name="遗留项", record=item, before=before)
    return success_response(to_dict(item), message="遗留项更新成功")


@router.delete("/legacy-items/{item_id}")
async def delete_legacy_item(item_id: int, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(TWLegacyItem).where(TWLegacyItem.id == item_id, TWLegacyItem.is_deleted == False))).scalar_one_or_none()
    if not item:
        raise UnifiedException(code=400, message="遗留项不存在")
    await ensure_manage_workbench_record(db, current_user, item)
    before = snapshot_workbench_record(item)
    soft_delete_workbench_record(item, current_user.id, beijing_now())
    await db.commit()
    await _audit_workbench_mutation(db, current_user, operation="删除", asset_name="遗留项", record=item, before=before)
    return success_response(message="遗留项删除成功")
