"""AI 长耗时调用共用的流式透传工具。"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from core.response import UnifiedException

logger = logging.getLogger(__name__)


def _ndjson(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, default=str) + "\n").encode("utf-8")


AI_STREAM_HEARTBEAT_SECONDS = 30.0
AI_STREAM_HEARTBEAT_MESSAGE = "AI正在处理中，请稍候"


async def stream_ai_call(
    call: Callable[[Callable[[dict], Awaitable[None]]], Awaitable[Any]],
    on_success: Callable[[Any], Awaitable[None]] | None = None,
    on_error: Callable[[str, bool], Awaitable[None]] | None = None,
    *,
    heartbeat_seconds: float = AI_STREAM_HEARTBEAT_SECONDS,
    heartbeat: bool = True,
    unwrap_unified_response: bool = False,
    include_error_data: bool = False,
):
    """把耗时 AI 调用包装成带 30 秒探活消息的 NDJSON 流。

    这里不改变 AI 调用本身，只负责在没有新内容时定时发一条很小的消息，
    让浏览器和网关知道连接仍在工作。默认不拆解业务结果，避免影响已有的
    流式调用；需要复用统一响应格式的接口可显式打开 ``unwrap_unified_response``。
    """
    queue: asyncio.Queue[dict] = asyncio.Queue()
    model_call_started = False

    async def emit(event: dict) -> None:
        nonlocal model_call_started
        if event.get("type") == "call_start":
            model_call_started = True
        await queue.put(event)

    async def _run_on_error(message: str) -> None:
        if on_error is None:
            return
        try:
            await on_error(message, model_call_started)
        except Exception:  # noqa: BLE001 - 清理失败不应覆盖原始错误
            logger.exception("AI 流式调用失败后的收尾失败")

    def _error_payload(exc: UnifiedException) -> dict:
        error_data = exc.data if isinstance(getattr(exc, "data", None), dict) else {}
        payload = {"type": "error", "message": exc.message, "code": exc.code}
        if include_error_data:
            # AI 导入接口的 data 只包含失败批次和用量等安全的业务摘要，
            # 前端需要它来保留原来的失败提示和用量展示。
            payload["data"] = error_data
        call_group_id = str(error_data.get("call_group_id") or "").strip()
        if call_group_id:
            payload["call_group_id"] = call_group_id[:100]
        failure_reason = str(error_data.get("failure_reason") or "").strip()
        if failure_reason:
            payload["failure_reason"] = failure_reason[:200]
        retry_candidates = error_data.get("retry_candidates")
        if isinstance(retry_candidates, list):
            payload["retry_candidates"] = [
                {
                    "id": item.get("id"),
                    "name": str(item.get("name") or "模型")[:100],
                    "model": str(item.get("model") or "")[:100],
                    "scope": str(item.get("scope") or "platform"),
                    "connectivity_status": str(item.get("connectivity_status") or "unknown"),
                    "reasoning_status": str(item.get("reasoning_status") or "unknown"),
                    "usage_status": str(item.get("usage_status") or "unknown"),
                    "quota_used": item.get("quota_used"),
                    "quota_limit": item.get("quota_limit"),
                    "quota_remaining": item.get("quota_remaining"),
                    "quota_scope": str(item.get("quota_scope") or ""),
                }
                for item in retry_candidates
                if isinstance(item, dict) and item.get("id") is not None
            ]
        for key in ("platform_model_unavailable", "quota_exhausted"):
            if key in error_data:
                payload[key] = bool(error_data[key])
        for key in ("current_model_scope", "current_model_name"):
            value = str(error_data.get(key) or "").strip()
            if value:
                payload[key] = value[:100]
        return payload

    task = asyncio.create_task(call(emit))
    try:
        # 先立即发一条，让浏览器和中间网关尽快确认连接已经建立；
        # 后续没有模型事件时，再按固定间隔发送探活消息。
        if heartbeat:
            yield _ndjson({
                "type": "event",
                "data": {
                    "type": "heartbeat",
                    "message": AI_STREAM_HEARTBEAT_MESSAGE,
                },
            })
        timeout = max(0.1, float(heartbeat_seconds))
        while not task.done():
            event_task = asyncio.create_task(queue.get())
            done, _pending = await asyncio.wait(
                {event_task, task},
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if event_task in done:
                yield _ndjson({"type": "event", "data": event_task.result()})
                continue
            event_task.cancel()
            await asyncio.gather(event_task, return_exceptions=True)
            if task in done:
                break
            elif heartbeat:
                yield _ndjson({
                    "type": "event",
                    "data": {
                        "type": "heartbeat",
                        "message": AI_STREAM_HEARTBEAT_MESSAGE,
                    },
                })
        while not queue.empty():
            yield _ndjson({"type": "event", "data": queue.get_nowait()})
        result = await task
        if on_success is not None:
            try:
                await on_success(result)
            except Exception:  # noqa: BLE001 - 收尾失败不影响已成功结果
                logger.exception("AI 流式成功后的收尾失败，不影响本次成功结果")
        if unwrap_unified_response and isinstance(result, dict) and "data" in result:
            yield _ndjson({
                "type": "complete",
                "code": result.get("code", 200),
                "message": result.get("message", ""),
                "data": result.get("data"),
            })
        else:
            yield _ndjson({"type": "complete", "data": result})
    except UnifiedException as exc:
        await _run_on_error(exc.message)
        logger.warning("AI 流式调用业务失败：code=%s, message=%s", exc.code, exc.message)
        yield _ndjson(_error_payload(exc))
    except Exception:  # noqa: BLE001
        await _run_on_error("AI 会话异常")
        logger.exception("AI 流式调用失败")
        yield _ndjson({
            "type": "error",
            "message": "AI 会话暂时无法继续，请重新开始本次对话后重试",
            "code": 500,
        })
    finally:
        if not task.done():
            task.cancel()
        # 无论客户端何时断开，都消费掉任务结果，避免后台留下
        # "Task exception was never retrieved"，也确保取消真正完成。
        await asyncio.gather(task, return_exceptions=True)


async def stream_requirement_ai_call(
    call: Callable[[Callable[[dict], Awaitable[None]]], Awaitable[dict]],
    on_success: Callable[[dict], Awaitable[None]],
    on_error: Callable[[str, bool], Awaitable[None]] | None = None,
):
    """兼容旧需求入口：沿用通用流处理，但保持原有无心跳输出。"""
    async for chunk in stream_ai_call(
        call,
        on_success,
        on_error,
        heartbeat_seconds=0.25,
        heartbeat=False,
    ):
        yield chunk
