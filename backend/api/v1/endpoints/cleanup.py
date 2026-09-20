"""
Data cleanup API endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import logging

from db.session import get_db
from models.models import User
from core.security import get_current_active_user
from core.response import success_response, UnifiedException
from core.timezone import beijing_now
from services.cleanup_service import (
    cleanup_soft_deleted_data,
    cleanup_single_table_data,
    build_cleanup_relation_display,
    get_all_table_relations,
    get_model_cleanup_tables,
    get_pending_cleanup_data,
    get_table_relations,
)
from utils.audit_logger import log_operation

logger = logging.getLogger(__name__)

router = APIRouter()

import time as _time

# 允许清理的表名白名单（来自当前模型元数据）
_valid_table_names = None
_valid_table_names_ts = 0  # 缓存时间戳
_CACHE_TTL = 300  # 缓存有效期5分钟


async def get_valid_table_names(db: AsyncSession) -> set:
    """获取当前模型中包含标准软删除字段的有效表名"""
    global _valid_table_names, _valid_table_names_ts
    if _valid_table_names is not None and (_time.time() - _valid_table_names_ts) < _CACHE_TTL:
        return _valid_table_names
    _valid_table_names = set(get_model_cleanup_tables())
    _valid_table_names_ts = _time.time()
    return _valid_table_names


async def validate_table_name(table_name: str, db: AsyncSession) -> str:
    """验证表名是否在白名单中，防止SQL注入"""
    valid = await get_valid_table_names(db)
    if table_name not in valid:
        raise UnifiedException(code=400, message=f"无效的表名: {table_name}")
    return table_name


class CleanupPreviewResponse(BaseModel):
    """清理预览响应"""
    tables: list[str]
    total_tables: int


@router.get("/preview")
async def preview_cleanup(
    mode: str = Query("datetime", regex="^(datetime|days)$", description="清理模式：datetime=按时间，days=按天数"),
    cutoff: str = Query(None, description="截止时间（ISO格式），mode=datetime时必填"),
    days: int = Query(7, ge=0, le=365, description="清理天数，mode=days时使用，0表示清理所有"),
    search_table: str = Query(None, description="搜索表名（英文）"),
    search_chinese: str = Query(None, description="搜索中文名称"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    预览可清理的表（仅超级管理员）
    
    Args:
        mode: 清理模式 - datetime(按时间) 或 days(按天数)
        cutoff: 截止时间（ISO 8601格式），如 2026-05-16T15:30:00
        days: 清理天数，0表示清理所有
        search_table: 搜索表名（英文）
        search_chinese: 搜索中文名称
    """
    if not current_user.is_superuser:
        raise UnifiedException(code=403, message="权限不足")
    
    # 计算 cutoff_time
    if mode == "datetime":
        if not cutoff:
            raise UnifiedException(code=400, message="按时间模式需要提供cutoff参数")
        try:
            cutoff_time = datetime.fromisoformat(cutoff)
        except ValueError:
            raise UnifiedException(code=400, message="cutoff时间格式错误，请使用ISO格式")
    else:  # mode == "days"
        if days == 0:
            # days=0 时，设置为一个很远的未来时间，相当于清理所有
            cutoff_time = datetime(9999, 12, 31, 23, 59, 59)
        else:
            cutoff_time = beijing_now() - timedelta(days=days)
    
    table_metadata = get_model_cleanup_tables()
    table_names = list(table_metadata)
    try:
        relation_map = await get_all_table_relations(db)
    except Exception as exc:
        logger.warning("读取清理关联关系失败，将继续返回表清单: %s", exc)
        relation_map = {}
    
    tables_info = []
    preview_errors = []
    for table_name in table_names:
        try:
            # 统计待清理数量：is_deleted=1 AND deleted_at有值 AND deleted_at <= cutoff
            count_sql = f"""
                SELECT COUNT(*) FROM `{table_name}` 
                WHERE is_deleted = 1 
                AND deleted_at IS NOT NULL
                AND deleted_at <= :cutoff_time
            """
            count_result = await db.execute(text(count_sql), {"cutoff_time": cutoff_time})
            pending_count = count_result.scalar() or 0
            
            chinese_name = table_metadata[table_name]["chinese_name"]
            
            # 前端搜索过滤（支持表名和中文名）
            if search_table:
                if search_table.lower() not in table_name.lower():
                    continue
            if search_chinese:
                if search_chinese.lower() not in chinese_name.lower():
                    continue
            
            tables_info.append({
                "table_name": table_name,
                "chinese_name": chinese_name,
                "pending_count": pending_count,
                "has_relations": bool(relation_map.get(table_name)),
            })
        except Exception as e:
            logger.error(f"Failed to count pending data for table {table_name}: {str(e)}")
            preview_errors.append(table_name)

    if preview_errors:
        raise UnifiedException(
            code=500,
            message="清理预览统计失败，请稍后重试",
            data={"failed_tables": preview_errors},
        )
    
    return success_response(
        data={
            "tables": tables_info,
            "total_tables": len(tables_info),
            "cutoff_time": cutoff_time.isoformat(),
            "mode": mode
        },
        message=f"找到 {len(tables_info)} 个包含软删除字段的表"
    )


@router.get("/preview/{table_name}")
async def preview_table_data(
    table_name: str,
    mode: str = Query("datetime", regex="^(datetime|days)$", description="清理模式"),
    cutoff: str = Query(None, description="截止时间（ISO格式）"),
    days: int = Query(7, ge=0, le=365, description="清理天数"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    查看指定表的待清理数据（仅超级管理员）
    
    Args:
        table_name: 表名
        mode: 清理模式
        cutoff: 截止时间
        days: 清理天数
    """
    if not current_user.is_superuser:
        raise UnifiedException(code=403, message="权限不足")

    await validate_table_name(table_name, db)

    # 计算 cutoff_time
    if mode == "datetime":
        if not cutoff:
            raise UnifiedException(code=400, message="按时间模式需要提供cutoff参数")
        try:
            cutoff_time = datetime.fromisoformat(cutoff)
        except ValueError:
            raise UnifiedException(code=400, message="cutoff时间格式错误")
    else:  # mode == "days"
        if days == 0:
            cutoff_time = datetime(9999, 12, 31, 23, 59, 59)
        else:
            cutoff_time = beijing_now() - timedelta(days=days)

    result = await get_pending_cleanup_data(db=db, table_name=table_name, cutoff_time=cutoff_time)
    
    if not result["success"]:
        raise UnifiedException(code=400, message=result.get("error", "查询失败"))
    
    try:
        result["relations"] = [
            build_cleanup_relation_display(relation)
            for relation in await get_table_relations(db, table_name, cutoff_time)
        ]
    except Exception as exc:
        logger.warning("读取表关联关系失败: %s", exc)
        result["relations"] = []
    result["chinese_name"] = get_model_cleanup_tables().get(table_name, {}).get("chinese_name", "")

    return success_response(
        data=result,
        message=f"表 {table_name} 共有 {result['total_count']} 条待清理数据"
    )


@router.post("/cleanup")
async def cleanup_data(
    mode: str = Query("datetime", regex="^(datetime|days)$", description="清理模式"),
    cutoff: str = Query(None, description="截止时间（ISO格式）"),
    days: int = Query(7, ge=0, le=365, description="清理天数，0表示清理所有"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    清理所有表的软删除数据（仅超级管理员）
    
    Args:
        mode: 清理模式 - datetime(按时间) 或 days(按天数)
        cutoff: 截止时间（ISO 8601格式）
        days: 清理天数，0表示清理所有
    """
    if not current_user.is_superuser:
        raise UnifiedException(code=403, message="权限不足")
    
    # 计算 cutoff_time
    if mode == "datetime":
        if not cutoff:
            raise UnifiedException(code=400, message="按时间模式需要提供cutoff参数")
        try:
            cutoff_time = datetime.fromisoformat(cutoff)
        except ValueError:
            raise UnifiedException(code=400, message="cutoff时间格式错误")
    else:  # mode == "days"
        if days == 0:
            cutoff_time = datetime(9999, 12, 31, 23, 59, 59)
        else:
            cutoff_time = beijing_now() - timedelta(days=days)
    
    # days=0 时特别警告
    if mode == "days" and days == 0:
        logger.warning(f"User {current_user.id} is attempting to clean ALL soft-deleted data (days=0)")
    
    result = await cleanup_soft_deleted_data(db=db, cutoff_time=cutoff_time)
    if not result.get("success", False):
        raise UnifiedException(code=500, message=result.get("message") or "物理清理失败")
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.nick_name or "未知用户",
        module="data_cleanup",
        operation="物理清理",
        target_name="平台数据",
        description="执行平台软删除数据物理清理",
        details={
            "mode": mode,
            "cutoff_time": cutoff_time.isoformat(),
            "tables_cleaned": result.get("tables_cleaned", 0),
            "total_records_deleted": result.get("total_records_deleted", 0),
        },
    )
    
    return success_response(
        data=result,
        message=result["message"]
    )


@router.post("/cleanup/{table_name}")
async def cleanup_single_table(
    table_name: str,
    mode: str = Query("datetime", regex="^(datetime|days)$", description="清理模式"),
    cutoff: str = Query(None, description="截止时间（ISO格式）"),
    days: int = Query(7, ge=0, le=365, description="清理天数，0表示清理所有"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    清理单个表的软删除数据（仅超级管理员）
    
    Args:
        table_name: 表名
        mode: 清理模式
        cutoff: 截止时间
        days: 清理天数
    """
    if not current_user.is_superuser:
        raise UnifiedException(code=403, message="权限不足")

    await validate_table_name(table_name, db)

    # 计算 cutoff_time
    if mode == "datetime":
        if not cutoff:
            raise UnifiedException(code=400, message="按时间模式需要提供cutoff参数")
        try:
            cutoff_time = datetime.fromisoformat(cutoff)
        except ValueError:
            raise UnifiedException(code=400, message="cutoff时间格式错误")
    else:  # mode == "days"
        if days == 0:
            cutoff_time = datetime(9999, 12, 31, 23, 59, 59)
        else:
            cutoff_time = beijing_now() - timedelta(days=days)

    result = await cleanup_single_table_data(db=db, table_name=table_name, cutoff_time=cutoff_time)
    if not result.get("success", False):
        raise UnifiedException(code=500, message=result.get("error") or result.get("message") or "物理清理失败")
    # 审计只展示业务名称，数据库表名仅留在详情里供排查。
    business_name = (get_model_cleanup_tables().get(table_name) or {}).get("chinese_name") or table_name
    await log_operation(
        db=db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.nick_name or "未知用户",
        module="data_cleanup",
        operation="物理清理",
        target_name=business_name,
        description=f"物理清理{business_name}的软删除数据",
        details={
            "cutoff_time": cutoff_time.isoformat(),
            "records_deleted": result.get("records_deleted", 0),
            "table_name": table_name,
        },
    )
    return success_response(
        data=result,
        message=result.get("message", "清理完成")
    )
