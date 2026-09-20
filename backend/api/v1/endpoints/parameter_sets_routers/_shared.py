"""参数集 / 参数项接口共用的依赖、schema 与工具。

从 api/v1/endpoints/parameter_sets.py 逐段搬运而来，不改变任何行为。
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions import ensure_project_access, ensure_project_asset_manage
from core.response import UnifiedException
from models.models import ParameterSet, ParameterItem, Project, User
from services.parameter_typing import validate_parameter_value


async def _ensure_project_manage_permission(db: AsyncSession, project_id: int, current_user: User) -> Project:
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)
    return project


async def _ensure_project_access_permission(db: AsyncSession, project_id: int, current_user: User) -> Project:
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    )).scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_access(current_user, project)
    return project


async def _ensure_parameter_set_manage_permission(db: AsyncSession, ps: ParameterSet, current_user: User) -> Project:
    return await _ensure_project_manage_permission(db, ps.project_id, current_user)


def _display_name_conflicts(items, display_name: str, current_item_id: int | None = None) -> bool:
    normalized = (display_name or "").strip()
    if not normalized:
        return False
    for item in items:
        if current_item_id is not None and getattr(item, "id", None) == current_item_id:
            continue
        if (getattr(item, "display_name", "") or "").strip() == normalized:
            return True
    return False


def _key_conflicts(items, key: str, current_item_id: int | None = None) -> bool:
    normalized = (key or "").strip()
    if not normalized:
        return False
    for item in items:
        if current_item_id is not None and getattr(item, "id", None) == current_item_id:
            continue
        if (getattr(item, "key", "") or "").strip() == normalized:
            return True
    return False


async def _active_items_for_parameter_set(db: AsyncSession, ps_id: int):
    result = await db.execute(
        select(ParameterItem).where(
            ParameterItem.parameter_set_id == ps_id,
            ParameterItem.is_deleted == False
        )
    )
    return result.scalars().all()


def _ensure_unique_display_names(items) -> None:
    seen = set()
    for item in items:
        name = item.display_name.strip()
        if name in seen:
            raise UnifiedException(code=400, message=f"参数名称「{name}」已存在")
        seen.add(name)


def _ensure_unique_keys(items) -> None:
    seen = set()
    for item in items:
        key = item.key.strip()
        if key in seen:
            raise UnifiedException(code=400, message=f"Key「{key}」已存在")
        seen.add(key)


class ParameterItemSchema(BaseModel):
    display_name: str
    key: str
    value: str
    type: str = "string"
    type_source: str = "manual"
    description: str | None = None
    sort_order: int = 0

    @field_validator("display_name", "key")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("参数名称和 Key 不能为空")
        return value.strip()

    @model_validator(mode="after")
    def value_matches_type(self):
        error = validate_parameter_value(self.type, self.value)
        if error:
            raise ValueError(error)
        return self


class ParameterSetCreate(BaseModel):
    name: str
    description: str | None = None
    project_id: int
    items: list[ParameterItemSchema] = Field(default_factory=list)


class ParameterSetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    items: list[ParameterItemSchema] | None = None


class ItemCreate(BaseModel):
    display_name: str
    key: str
    value: str
    type: str = "string"
    type_source: str = "manual"
    description: str | None = None
    sort_order: int = 0

    @field_validator("display_name", "key")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("参数名称和 Key 不能为空")
        return value.strip()

    @model_validator(mode="after")
    def value_matches_type(self):
        error = validate_parameter_value(self.type, self.value)
        if error:
            raise ValueError(error)
        return self


class ItemUpdate(BaseModel):
    display_name: str | None = None
    key: str | None = None
    value: str | None = None
    type: str | None = None
    type_source: str | None = None
    description: str | None = None
    sort_order: int | None = None

    @field_validator("display_name", "key")
    @classmethod
    def optional_required_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("参数名称和 Key 不能为空")
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def value_matches_type(self):
        if self.value is not None:
            error = validate_parameter_value(self.type or "string", self.value)
            if error:
                raise ValueError(error)
        return self
