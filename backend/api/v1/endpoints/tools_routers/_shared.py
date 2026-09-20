"""工具箱各功能模块共用的导入与依赖。

集中转出常用的 FastAPI / 核心依赖，供各子路由按需引入，避免重复样板导入。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.response import UnifiedException, success_response
from core.security import get_current_active_user
from core.timezone import beijing_now
from db.session import get_db
from utils.audit_logger import log_operation, log_user_operation, safe_host_target

__all__ = [
    "APIRouter",
    "Depends",
    "File",
    "Request",
    "UploadFile",
    "StreamingResponse",
    "BaseModel",
    "AsyncSession",
    "UnifiedException",
    "success_response",
    "get_current_active_user",
    "beijing_now",
    "get_db",
    "log_operation",
    "log_user_operation",
    "safe_host_target",
]
