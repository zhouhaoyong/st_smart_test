"""测试工作台活动记录的公共读取能力。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from models.models import TWSystem, TWVersion, User


async def get_active_workbench_record(
    db: AsyncSession,
    model: type,
    record_id: int,
    *,
    not_found_message: str,
    not_found_code: int = 400,
) -> Any:
    """按模型和主键读取未软删除记录，保留调用方自己的业务错误文案。"""
    record = (await db.execute(
        select(model).where(model.id == record_id, model.is_deleted == False)
    )).scalar_one_or_none()
    if not record:
        raise UnifiedException(code=not_found_code, message=not_found_message)
    return record


async def ensure_scoped_unique_value(
    db: AsyncSession,
    model: type,
    *,
    scope_field: str,
    scope_id: int,
    field_name: str,
    value: str | None,
    label: str,
    scope_label: str = "范围",
    exclude_id: int | None = None,
) -> None:
    """检查活动记录在指定范围内的文本唯一性。"""
    normalized = str(value or "").strip()
    if not normalized:
        return

    scope_column = getattr(model, scope_field)
    value_column = getattr(model, field_name)
    statement = select(model.id).where(
        scope_column == scope_id,
        func.trim(value_column) == normalized,
        model.is_deleted == False,
    )
    if exclude_id is not None:
        statement = statement.where(model.id != exclude_id)
    if (await db.execute(statement)).scalar_one_or_none() is not None:
        raise UnifiedException(code=400, message=f"当前{scope_label}内{label}已存在，请勿重复填写")


async def get_workbench_readonly_metadata(db: AsyncSession, record: Any) -> dict[str, str]:
    """读取工作台详情页共用的系统、版本和创建人展示信息。"""
    system = (await db.execute(
        select(TWSystem).where(TWSystem.id == record.system_id)
    )).scalar_one_or_none()
    version = (await db.execute(
        select(TWVersion).where(TWVersion.id == record.version_id)
    )).scalar_one_or_none()
    creator = None
    if getattr(record, "created_by", None):
        creator = (await db.execute(
            select(User).where(User.id == record.created_by)
        )).scalar_one_or_none()
    return {
        "system_name": getattr(system, "name", ""),
        "version_no": getattr(version, "version_no", ""),
        "creator_name": getattr(creator, "real_name", "") or getattr(creator, "nick_name", ""),
    }
