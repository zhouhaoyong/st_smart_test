"""Cron 表达式生成与解析工具接口。"""
from __future__ import annotations

from services.cron_tool_service import CronToolError, analyze_cron, generate_cron

from ._shared import (
    APIRouter,
    BaseModel,
    Depends,
    UnifiedException,
    get_current_active_user,
    get_db,
    AsyncSession,
    log_user_operation,
    success_response,
)

router = APIRouter()


# ====== Cron 工具 ======


class CronGenerateRequest(BaseModel):
    cron_format: str = "standard"
    frequency: str = "minutes"
    interval: int = 1
    minute: int = 0
    hour: int = 0
    weekdays: list[int] | None = None
    day_of_month: int = 1


class CronAnalyzeRequest(BaseModel):
    expression: str
    cron_format: str = "standard"


@router.post("/cron/generate")
async def cron_generate(
    data: CronGenerateRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = generate_cron(
            cron_format=data.cron_format,
            frequency=data.frequency,
            interval=data.interval,
            minute=data.minute,
            hour=data.hour,
            weekdays=data.weekdays,
            day_of_month=data.day_of_month,
        )
        await log_user_operation(
            db=db, user=current_user, module="cron_tool", operation="生成",
            target_name="Cron 表达式", description="生成 Cron 表达式",
        )
        return success_response(data=result, message="生成成功")
    except CronToolError as exc:
        await log_user_operation(
            db=db, user=current_user, module="cron_tool", operation="生成",
            target_name="Cron 表达式", description="生成 Cron 表达式失败",
            details={"status": "failed"},
        )
        raise UnifiedException(code=400, message=str(exc))


@router.post("/cron/analyze")
async def cron_analyze(
    data: CronAnalyzeRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = analyze_cron(
            expression=data.expression,
            cron_format=data.cron_format,
        )
        await log_user_operation(
            db=db, user=current_user, module="cron_tool", operation="解析",
            target_name="Cron 表达式", description="解析 Cron 表达式",
        )
        return success_response(data=result, message="解析成功")
    except CronToolError as exc:
        await log_user_operation(
            db=db, user=current_user, module="cron_tool", operation="解析",
            target_name="Cron 表达式", description="解析 Cron 表达式失败",
            details={"status": "failed"},
        )
        raise UnifiedException(code=400, message=str(exc))
