"""
Audit Log API endpoints
"""
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from db.session import get_db
from models.models import User
from core.security import get_current_active_user
from core.response import success_response, UnifiedException
from services.audit_service import create_audit_log, get_audit_logs, soft_delete_audit_logs
from utils.audit_logger import get_request_ip
from utils.oss_client import resolve_file_url

router = APIRouter()


class AuditLogIdsRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class AuditLogFilterDeleteRequest(BaseModel):
    user_id: Optional[int] = None
    module: list[str] = Field(default_factory=list)
    operation: list[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@router.get("/")
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    module: list[str] | None = Query(None),
    operation: list[str] | None = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取审计日志列表（仅超级管理员）"""
    if not current_user.is_superuser:
        raise UnifiedException(code=403, message="权限不足")
    
    logs, total = await get_audit_logs(
        db=db,
        skip=skip,
        limit=limit,
        user_id=user_id,
        module=module,
        operation=operation,
        start_time=start_time,
        end_time=end_time,
    )
    user_ids = {log.user_id for log in logs if log.user_id}
    user_avatar_map = {}
    if user_ids:
        user_result = await db.execute(
            select(User.id, User.avatar).where(User.id.in_(user_ids))
        )
        user_avatar_map = {
            row.id: resolve_file_url(row.avatar)
            for row in user_result.all()
        }
    
    return success_response(
        data={
            "items": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "user_name": log.user_name,
                    "user_avatar": user_avatar_map.get(log.user_id),
                    "module": log.module,
                    "operation": log.operation,
                    "target_id": log.target_id,
                    "target_name": log.target_name,
                    "description": log.description,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
            "total": total,
        }
    )


@router.post("/delete-batch")
async def delete_audit_logs_batch(
    data: AuditLogIdsRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """超管批量软删除已选审计日志。"""
    if not current_user.is_superuser:
        raise UnifiedException(code=403, message="权限不足")
    deleted_count = await soft_delete_audit_logs(db, ids=data.ids)
    await create_audit_log(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="审计日志",
        operation="审计日志清理",
        description=f"删除审计日志 {deleted_count} 条",
        ip_address=get_request_ip(request),
    )
    return success_response(data={"deleted_count": deleted_count}, message=f"已删除 {deleted_count} 条审计日志")


@router.post("/delete-all")
async def delete_audit_logs_all(
    data: AuditLogFilterDeleteRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """超管按当前筛选条件软删除全部审计日志。"""
    if not current_user.is_superuser:
        raise UnifiedException(code=403, message="权限不足")
    deleted_count = await soft_delete_audit_logs(
        db=db,
        user_id=data.user_id,
        module=data.module,
        operation=data.operation,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    await create_audit_log(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name,
        module="审计日志",
        operation="审计日志清理",
        description=f"删除审计日志 {deleted_count} 条",
        ip_address=get_request_ip(request),
    )
    return success_response(data={"deleted_count": deleted_count}, message=f"已删除 {deleted_count} 条审计日志")
