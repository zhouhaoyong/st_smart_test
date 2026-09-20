"""Shared database and serialization helpers used by API testing and UI testing modules."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException
from models.models import User
from utils.oss_client import resolve_file_url


async def get_or_404(db: AsyncSession, model, obj_id: int, message: str):
    """Fetch a single row by primary key with soft-delete filter.
    
    Raises UnifiedException(code=404) when the row does not exist or is soft-deleted.
    """
    result = await db.execute(select(model).where(model.id == obj_id, model.is_deleted == False))
    obj = result.scalar_one_or_none()
    if not obj:
        raise UnifiedException(code=404, message=message)
    return obj


def row_to_dict(row, extra: dict[str, Any] | None = None) -> dict:
    """Convert an ORM model instance to a plain dict using its table columns.
    
    Optionally merge *extra* key-value pairs into the result.
    """
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    if extra:
        data.update(extra)
    return data


def owner_info(user: User | None) -> dict[str, Any] | None:
    """Serialize a User object into a lightweight owner dict."""
    if not user:
        return None
    return {
        "id": user.id,
        "real_name": user.real_name,
        "nick_name": user.nick_name,
        "avatar": resolve_file_url(user.avatar),
    }
