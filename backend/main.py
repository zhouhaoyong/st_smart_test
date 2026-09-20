import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.v1.endpoints import api_router
from core.config import settings
from core.logging_config import configure_error_logging
from core.response import (
    UnifiedException,
    build_error_log_message,
    http_exception_handler,
    unified_exception_handler,
    validation_exception_handler,
)
from utils.audit_logger import bind_audit_request, reset_audit_request
from services.schedule_runner import start_schedule_runner, stop_schedule_runner
import models.ai_models  # noqa: F401  ensure AI shared tables are registered
import models.audit_log  # noqa: F401
import uvicorn
import asyncio
import logging

import os
from fastapi.staticfiles import StaticFiles

configure_error_logging()
# Suppress noisy SQLAlchemy engine INFO logs (they flood console during AI analysis)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Ensure upload directories exist
os.makedirs('uploads/avatars', exist_ok=True)
os.makedirs('uploads/feedbacks', exist_ok=True)

app = FastAPI(
    title=settings.APP_TITLE,
    root_path=settings.ROOT_PATH,
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
)

# Mount uploads as static files (must be after app creation, before API routes)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 配置 CORS（通过环境变量 BACKEND_CORS_ORIGINS 控制，默认 '*'）
cors_origins = settings.get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def bind_audit_request_context(request: Request, call_next):
    """让所有请求内的审计记录都能继承当前请求来源 IP。"""
    token = bind_audit_request(request)
    try:
        return await call_next(request)
    finally:
        reset_audit_request(token)

# 注册异常处理器
app.add_exception_handler(UnifiedException, unified_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    content = {
        "code": 500,
        "message": "服务异常，您可通过头像下拉菜单提交问题反馈或找管理员进行处理",
        "data": None,
    }
    logger.error(await build_error_log_message(
        request,
        title="未处理异常",
        response_content=content,
        exception=exc,
        include_traceback=True,
    ))
    return JSONResponse(status_code=200, content=content)

# Include API routers
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup():
    """应用启动时启动定时执行器。数据库初始化由部署入口显式执行。"""
    await start_schedule_runner()

@app.on_event("shutdown")
async def shutdown():
    await stop_schedule_runner()

@app.get("/")
async def root():
    return {"message": "API Auto Test Platform"}

@app.get("/health")
async def health():
    """服务健康检查"""
    return {"status": "ok", "version": settings.APP_VERSION, "title": settings.APP_TITLE}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
