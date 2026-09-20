"""接口列表 AI 用例生成的临时预览共享存储。

预览内容需要跨多个请求保存，不能依赖某个后端进程的内存；这里使用现有业务数据库，
让多实例之间共享同一份预览，并沿用用户、项目归属校验、过期和软删除规则。
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.timezone import beijing_now
from models.models import AiImportPreview

PREVIEW_TTL_SECONDS = 2 * 60 * 60
MAX_PREVIEW_ENTRIES = 200


class PreviewNotFoundError(Exception):
    """预览不存在（从未创建或已被删除）。"""


class PreviewExpiredError(Exception):
    """预览已过期，不能继续使用。"""


class PreviewForbiddenError(Exception):
    """预览不属于当前用户或当前项目。"""


class PreviewStore:
    """基于业务数据库的临时预览存储，支持多进程和多实例读取。"""

    def __init__(self, ttl_seconds: int = PREVIEW_TTL_SECONDS, capacity: int = MAX_PREVIEW_ENTRIES):
        self._ttl = ttl_seconds
        self._capacity = capacity

    @staticmethod
    def _now() -> datetime:
        # MySQL 的 DateTime 字段按当前项目约定以北京时间的无时区值落库。
        return beijing_now().replace(tzinfo=None)

    @staticmethod
    def _to_entry(row: AiImportPreview) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": int(row.user_id),
            "project_id": int(row.project_id),
            "created_at": row.created_at,
            "last_access": row.last_access_at,
            "expires_at": row.expires_at,
            "stage": row.stage,
            # 后续步骤会就地修改预览数据，必须与 ORM 实体隔离，避免嵌套 JSON
            # 先被改动、再赋回浅层副本时被 ORM 判定为未变化。
            "data": copy.deepcopy(row.payload) if isinstance(row.payload, dict) else {},
        }

    async def _purge_expired(self, db: AsyncSession, now: datetime) -> None:
        await db.execute(
            update(AiImportPreview)
            .where(
                AiImportPreview.is_deleted == False,
                AiImportPreview.expires_at <= now,
            )
            .values(is_deleted=True, deleted_at=now)
        )

    async def _evict_over_capacity(self, db: AsyncSession) -> None:
        preview_ids = (await db.execute(
            select(AiImportPreview.id)
            .where(AiImportPreview.is_deleted == False)
            .order_by(AiImportPreview.last_access_at.asc(), AiImportPreview.created_at.asc())
        )).scalars().all()
        overflow = len(preview_ids) - self._capacity
        if overflow <= 0:
            return
        now = self._now()
        await db.execute(
            update(AiImportPreview)
            .where(AiImportPreview.id.in_(preview_ids[:overflow]))
            .values(is_deleted=True, deleted_at=now)
        )

    async def create(self, db: AsyncSession, *, user_id: int, project_id: int, payload: dict[str, Any]) -> str:
        now = self._now()
        preview_id = uuid.uuid4().hex
        row = AiImportPreview(
            id=preview_id,
            user_id=int(user_id),
            project_id=int(project_id),
            payload=payload if isinstance(payload, dict) else {},
            stage=payload.get("stage", "parsed"),
            created_at=now,
            last_access_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
        )
        db.add(row)
        await self._purge_expired(db, now)
        await self._evict_over_capacity(db)
        await db.commit()
        return preview_id

    async def _get_row(
        self,
        db: AsyncSession,
        preview_id: str,
        *,
        for_update: bool = False,
    ) -> AiImportPreview:
        statement = select(AiImportPreview).where(
            AiImportPreview.id == preview_id,
            AiImportPreview.is_deleted == False,
        )
        if for_update:
            statement = statement.with_for_update()
        row = (await db.execute(statement)).scalar_one_or_none()
        if not row:
            raise PreviewNotFoundError("预览不存在或已失效，请重新上传")
        now = self._now()
        if row.expires_at <= now:
            row.is_deleted = True
            row.deleted_at = now
            await db.commit()
            raise PreviewExpiredError("预览已过期，请重新上传")
        return row

    async def get(self, db: AsyncSession, *, preview_id: str, user_id: int, project_id: int) -> dict[str, Any]:
        row = await self._get_row(db, preview_id)
        if row.user_id != int(user_id) or row.project_id != int(project_id):
            raise PreviewForbiddenError("无权访问该预览")
        row.last_access_at = self._now()
        await db.commit()
        return self._to_entry(row)

    async def get_for_update(
        self,
        db: AsyncSession,
        *,
        preview_id: str,
        user_id: int,
        project_id: int,
    ) -> dict[str, Any]:
        """读取并锁定预览，不更新访问时间或提交事务。"""
        row = await self._get_row(db, preview_id, for_update=True)
        if row.user_id != int(user_id) or row.project_id != int(project_id):
            raise PreviewForbiddenError("无权访问该预览")
        return self._to_entry(row)

    async def update(
        self,
        db: AsyncSession,
        *,
        preview_id: str,
        user_id: int,
        project_id: int,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        row = await self._get_row(db, preview_id)
        if row.user_id != int(user_id) or row.project_id != int(project_id):
            raise PreviewForbiddenError("无权访问该预览")
        data = copy.deepcopy(row.payload) if isinstance(row.payload, dict) else {}
        data.update(copy.deepcopy(patch) if isinstance(patch, dict) else {})
        row.payload = data
        if "stage" in patch:
            row.stage = patch["stage"]
        row.last_access_at = self._now()
        await db.commit()
        return self._to_entry(row)

    async def delete(
        self,
        db: AsyncSession,
        *,
        preview_id: str,
        user_id: int,
        project_id: int,
        commit: bool = True,
    ) -> None:
        try:
            row = await self._get_row(db, preview_id)
        except (PreviewNotFoundError, PreviewExpiredError):
            # 保存事务完成后预览可能已被并发请求或过期清理，结果已经达到失效目的。
            return
        if row.user_id != int(user_id) or row.project_id != int(project_id):
            raise PreviewForbiddenError("无权访问该预览")
        row.is_deleted = True
        row.deleted_at = self._now()
        if commit:
            await db.commit()


preview_store = PreviewStore()
