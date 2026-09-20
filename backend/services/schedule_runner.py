import asyncio
import logging
from contextlib import suppress

from sqlalchemy import select, update

from core.config import settings
from core.timezone import beijing_now
from db.session import AsyncSessionLocal
from models.models import ExecutionSet, Report, SchedulePolicy, ScheduleRunLog
from services.execution_engine import execute_execution_set
from services.report_sender import send_report_to_configured_channels
from services.schedule_utils import ensure_beijing, next_trigger_time

logger = logging.getLogger(__name__)

_runner_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_semaphore: asyncio.Semaphore | None = None


def resolve_schedule_execution_status(report_status: str | None) -> str:
    """把测试报告状态转换为调度运行状态。"""
    return "success" if report_status == "success" else "failed"


async def start_schedule_runner():
    global _runner_task, _stop_event, _semaphore
    if not settings.SCHEDULER_ENABLED:
        logger.info("Schedule runner disabled")
        return
    if _runner_task and not _runner_task.done():
        return
    _stop_event = asyncio.Event()
    _semaphore = asyncio.Semaphore(max(1, settings.SCHEDULER_MAX_CONCURRENT))
    _runner_task = asyncio.create_task(_run_loop())
    logger.info("Schedule runner started")


async def stop_schedule_runner():
    if _stop_event:
        _stop_event.set()
    if _runner_task:
        _runner_task.cancel()
        with suppress(asyncio.CancelledError):
            await _runner_task


async def _run_loop():
    poll_seconds = max(5, settings.SCHEDULER_POLL_SECONDS)
    while True:
        try:
            await _tick()
        except Exception as exc:
            logger.exception("Schedule runner tick failed: %s", exc)
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=poll_seconds)
            break
        except asyncio.TimeoutError:
            continue


async def _tick():
    now = beijing_now()
    db_now = now.replace(tzinfo=None)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SchedulePolicy)
            .where(
                SchedulePolicy.is_deleted == False,
                SchedulePolicy.is_enabled == True,
                SchedulePolicy.next_trigger_at.is_not(None),
                SchedulePolicy.next_trigger_at <= db_now,
            )
            .order_by(SchedulePolicy.next_trigger_at)
            .limit(20)
        )
        policies = result.scalars().all()

    for policy in policies:
        task = asyncio.create_task(_trigger_policy(policy.id))
        task.add_done_callback(_log_task_exception)


def _log_task_exception(task: asyncio.Task):
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc:
        logger.exception("Schedule policy task failed", exc_info=exc)


async def _trigger_policy(policy_id: int):
    now = beijing_now()
    db_now = now.replace(tzinfo=None)
    async with AsyncSessionLocal() as db:
        policy = await db.get(SchedulePolicy, policy_id)
        if not policy or policy.is_deleted or not policy.is_enabled:
            return
        next_trigger_at = ensure_beijing(policy.next_trigger_at) if policy.next_trigger_at else None
        if not next_trigger_at or next_trigger_at > now:
            return

        next_scheduled_at = next_trigger_time(
            policy.schedule_type,
            {**(policy.schedule_config or {}), "_last_triggered_at": now},
            policy.cron_expression,
            now,
        )
        claim_result = await db.execute(
            update(SchedulePolicy)
            .where(
                SchedulePolicy.id == policy_id,
                SchedulePolicy.is_deleted == False,
                SchedulePolicy.is_enabled == True,
                SchedulePolicy.next_trigger_at <= db_now,
            )
            .values(
                last_triggered_at=now,
                last_status="triggered",
                last_summary={"total": 0, "triggered": 0, "skipped": 0, "failed": 0},
                next_trigger_at=next_scheduled_at,
            )
        )
        # 多个实例可能同时读到同一条到期策略，只有成功更新的一方可以继续执行。
        if claim_result.rowcount != 1:
            return

        result = await db.execute(
            select(ExecutionSet)
            .where(
                ExecutionSet.schedule_policy_id == policy_id,
                ExecutionSet.is_deleted == False,
                ExecutionSet.is_enabled == True,
            )
            .order_by(ExecutionSet.id)
        )
        execution_sets = result.scalars().all()
        policy.last_summary = {"total": len(execution_sets), "triggered": 0, "skipped": 0, "failed": 0}
        for execution_set in execution_sets:
            execution_set.next_scheduled_run_at = next_scheduled_at
        await db.commit()

    triggered = skipped = failed = 0
    tasks = []
    for execution_set in execution_sets:
        if execution_set.scheduler_status == "running":
            skipped += 1
            await _write_skip_log(policy_id, execution_set.id, "上一次定时执行尚未结束，本次跳过")
            continue
        tasks.append(asyncio.create_task(_run_execution(policy_id, execution_set.id)))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for item in results:
            if isinstance(item, Exception):
                failed += 1
            elif item == "success":
                triggered += 1
            elif item == "skipped":
                skipped += 1
            else:
                failed += 1

    async with AsyncSessionLocal() as db:
        policy = await db.get(SchedulePolicy, policy_id)
        if policy:
            policy.last_status = "success" if failed == 0 else "failed"
            policy.last_summary = {
                "total": len(execution_sets),
                "triggered": triggered,
                "skipped": skipped,
                "failed": failed,
            }
            await db.commit()


async def _write_skip_log(policy_id: int, execution_set_id: int, detail: str):
    async with AsyncSessionLocal() as db:
        log = ScheduleRunLog(
            policy_id=policy_id,
            execution_set_id=execution_set_id,
            status="skipped",
            message_status="skipped",
            detail=detail,
            finished_at=beijing_now(),
        )
        db.add(log)
        execution_set = await db.get(ExecutionSet, execution_set_id)
        if execution_set:
            execution_set.scheduler_status = "idle"
            execution_set.scheduler_error = detail
        await db.commit()


async def _run_execution(policy_id: int, execution_set_id: int) -> str:
    async with _semaphore:
        log_id = None
        report_id = None
        async with AsyncSessionLocal() as db:
            execution_set = await db.get(ExecutionSet, execution_set_id)
            policy = await db.get(SchedulePolicy, policy_id)
            if (
                not execution_set
                or execution_set.is_deleted
                or execution_set.scheduler_status == "running"
                or not execution_set.is_enabled
                or not policy
                or policy.is_deleted
                or not policy.is_enabled
                or execution_set.schedule_policy_id != policy_id
            ):
                return "skipped"
            execution_set.scheduler_status = "running"
            execution_set.scheduler_started_at = beijing_now()
            execution_set.scheduler_error = None
            execution_set.last_scheduled_run_at = beijing_now()
            log = ScheduleRunLog(policy_id=policy_id, execution_set_id=execution_set_id, status="running")
            db.add(log)
            await db.commit()
            await db.refresh(log)
            log_id = log.id

        status = "success"
        detail = "执行完成"
        message_status = "skipped"
        message_detail = "未配置消息发送信息"
        try:
            async with AsyncSessionLocal() as db:
                report_id = await execute_execution_set(execution_set_id, db)

            async with AsyncSessionLocal() as db:
                report_status = (await db.execute(
                    select(Report.status).where(
                        Report.id == report_id,
                        Report.is_deleted == False,
                    )
                )).scalar_one_or_none()
            status = resolve_schedule_execution_status(report_status)
            if status != "success":
                detail = "测试报告失败"

            async with AsyncSessionLocal() as db:
                try:
                    results = await send_report_to_configured_channels(
                        report_id,
                        db,
                        frontend_url=settings.FRONTEND_BASE_URL,
                        raise_when_no_channels=False,
                    )
                    if results:
                        message_status = "failed" if any(item.get("status") == "failed" for item in results) else "success"
                        message_detail = "; ".join(f"{item.get('channel')}:{item.get('detail')}" for item in results)
                except Exception as exc:
                    message_status = "failed"
                    message_detail = str(exc)[:500]
        except Exception as exc:
            logger.exception("Scheduled execution failed, execution_set_id=%s", execution_set_id)
            status = "failed"
            detail = str(exc)[:500]

        async with AsyncSessionLocal() as db:
            execution_set = await db.get(ExecutionSet, execution_set_id)
            policy = await db.get(SchedulePolicy, policy_id)
            if execution_set:
                schedule_available = bool(
                    policy
                    and not policy.is_deleted
                    and policy.is_enabled
                    and execution_set.is_enabled
                    and execution_set.schedule_policy_id == policy_id
                )
                execution_set.scheduler_status = (
                    "idle" if status == "success" else "error"
                ) if schedule_available else "disabled"
                execution_set.scheduler_error = (
                    None if status == "success" else detail
                ) if schedule_available else "执行策略已停用"
                execution_set.next_scheduled_run_at = None
                execution_set.scheduler_started_at = None
            if log_id:
                log = await db.get(ScheduleRunLog, log_id)
                if log:
                    log.status = status
                    log.report_id = report_id
                    log.message_status = message_status
                    log.message_detail = message_detail
                    log.detail = detail
                    log.finished_at = beijing_now()
            await db.commit()
        return status
