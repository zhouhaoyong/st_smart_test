"""Shared in-memory stream bus for long-running AI tasks."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from services.ai_billing_service import format_task_cost_text

MAX_STREAM_EVENTS = 300

_streams: dict[int, dict[str, Any]] = {}


def _format_cost_text(amount: float | None) -> str | None:
    return format_task_cost_text(amount)


def _billing_amount(billing: Any) -> float | None:
    if not isinstance(billing, dict):
        return None
    value = billing.get("amount")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_billing_summary(calls: list[dict[str, Any]]) -> dict[str, Any]:
    call_count = len([item for item in calls if item.get("call_id")])
    billed_calls = []
    total = 0.0
    has_amount = False
    has_enabled = False
    for item in calls:
        billing = item.get("billing") if isinstance(item.get("billing"), dict) else None
        if not billing:
            continue
        has_enabled = has_enabled or bool(billing.get("enabled"))
        amount = _billing_amount(billing)
        if amount is not None:
            has_amount = True
            total += amount
        billed_calls.append({
            "call_id": item.get("call_id"),
            "sequence": item.get("sequence"),
            "title": item.get("title"),
            "audit_action": item.get("audit_action"),
            "feature": item.get("feature"),
            "model_name": item.get("model_name"),
            "amount": amount,
            "text": billing.get("text"),
            "billing": billing,
        })
    amount_value = round(total, 6) if has_amount else None
    text = format_task_cost_text(amount_value, call_count) if has_amount else None
    return {
        "enabled": has_enabled,
        "amount": amount_value,
        "text": text,
        "call_count": call_count,
        "calls": billed_calls,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_stream(task_id: int) -> dict[str, Any]:
    state = _streams.get(task_id)
    if state is None:
        state = {
            "task_id": task_id,
            "seq": 0,
            "status": "running",
            "input_text": "",
            "output_text": "",
            "reasoning_text": "",
            "stage": "",
            "calls": [],
            "call_map": {},
            "billing_summary_override": None,
            "events": [],
            "subscribers": set(),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        _streams[task_id] = state
    return state


def start_ai_task_stream(task_id: int, *, title: str = "", stage: str = "") -> None:
    state = _get_stream(task_id)
    state.update({
        "seq": 0,
        "status": "running",
        "input_text": "",
        "output_text": "",
        "reasoning_text": "",
        "stage": stage,
        "calls": [],
        "call_map": {},
        "billing_summary_override": None,
        "events": [],
        "title": title,
        "updated_at": _now_iso(),
    })
    publish_ai_task_event(task_id, "stage", message=stage or title or "AI 任务已开始")


def get_ai_task_stream_snapshot(task_id: int) -> dict[str, Any]:
    state = _get_stream(task_id)
    calls = state.get("calls") or []
    billing_summary = state.get("billing_summary_override") or _build_billing_summary(calls)
    return {
        "type": "snapshot",
        "task_id": task_id,
        "seq": state["seq"],
        "status": state.get("status") or "running",
        "stage": state.get("stage") or "",
        "input_text": state.get("input_text") or "",
        "output_text": state.get("output_text") or "",
        "reasoning_text": state.get("reasoning_text") or "",
        "text": state.get("output_text") or "",
        "calls": calls,
        "billing_summary": billing_summary,
        "updated_at": state.get("updated_at") or _now_iso(),
    }


def get_ai_task_stream_summary(task_id: int) -> dict[str, Any]:
    state = _get_stream(task_id)
    calls = state.get("calls") or []
    return {
        "calls": calls,
        "billing_summary": state.get("billing_summary_override") or _build_billing_summary(calls),
    }


def set_ai_task_billing_summary(task_id: int, summary: dict[str, Any] | None) -> None:
    state = _get_stream(task_id)
    state["billing_summary_override"] = summary if isinstance(summary, dict) else None
    state["updated_at"] = _now_iso()


def _get_call_state(state: dict[str, Any], data: dict[str, Any], stage: str = "") -> dict[str, Any] | None:
    call_id = str(data.get("call_id") or "").strip()
    if not call_id:
        return None
    call_map = state.setdefault("call_map", {})
    calls = state.setdefault("calls", [])
    call = call_map.get(call_id)
    if call is None:
        call = {
            "call_id": call_id,
            "sequence": len(calls) + 1,
            "title": data.get("call_title") or data.get("stage_name") or stage or data.get("audit_action") or "模型调用",
            "audit_action": data.get("audit_action"),
            "feature": data.get("feature"),
            "stage": stage,
            "status": "running",
            "input_text": "",
            "reasoning_text": "",
            "output_text": "",
            "model_attempts": [],
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        calls.append(call)
        call_map[call_id] = call
    if data.get("call_title") or data.get("stage_name"):
        call["title"] = data.get("call_title") or data.get("stage_name")
    if data.get("audit_action"):
        call["audit_action"] = data.get("audit_action")
    if data.get("feature"):
        call["feature"] = data.get("feature")
    if stage:
        call["stage"] = stage
    call["updated_at"] = _now_iso()
    return call


def _merge_model_attempt(call: dict[str, Any], data: dict[str, Any], status: str) -> None:
    sequence = data.get("sequence")
    attempts = call.setdefault("model_attempts", [])
    attempt = None
    for item in attempts:
        if item.get("sequence") == sequence:
            attempt = item
            break
    if attempt is None:
        attempt = {"sequence": sequence}
        attempts.append(attempt)
    attempt.update({
        "model_id": data.get("model_id"),
        "model_name": data.get("model_name"),
        "status": status,
    })
    if data.get("error"):
        attempt["error"] = data.get("error")
    if data.get("next_model_name"):
        attempt["next_model_name"] = data.get("next_model_name")


def publish_ai_task_event(
    task_id: int,
    event_type: str,
    *,
    delta: str = "",
    input_text: str = "",
    message: str = "",
    stage: str = "",
    status: str = "",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = _get_stream(task_id)
    data = data or {}
    event_at = _now_iso()
    if stage:
        state["stage"] = stage
    if status:
        state["status"] = status
    if input_text:
        state["input_text"] = input_text
    call = _get_call_state(state, data, stage)
    if event_type == "call_start" and call is not None:
        call["status"] = "running"
        call["started_at"] = event_at
        call["message"] = message
    if event_type == "input" and call is not None and input_text:
        call["input_text"] = input_text
    if delta:
        if event_type == "reasoning_delta":
            state["reasoning_text"] = (state.get("reasoning_text") or "") + delta
            if call is not None:
                call["reasoning_text"] = (call.get("reasoning_text") or "") + delta
        else:
            state["output_text"] = (state.get("output_text") or "") + delta
            if call is not None:
                call["output_text"] = (call.get("output_text") or "") + delta
    if event_type == "model_start" and call is not None:
        _merge_model_attempt(call, data, "running")
        call["model_id"] = data.get("model_id")
        call["model_name"] = data.get("model_name")
    if event_type == "model_success" and call is not None:
        _merge_model_attempt(call, data, "success")
        call["model_id"] = data.get("model_id")
        call["model_name"] = data.get("model_name")
    if event_type == "model_failed" and call is not None:
        _merge_model_attempt(call, data, "failed")
    if event_type == "call_complete" and call is not None:
        call["status"] = "success"
        call["ended_at"] = event_at
        if isinstance(data.get("billing"), dict):
            call["billing"] = data.get("billing")
        if isinstance(data.get("usage"), dict):
            call["usage"] = data.get("usage")
        if data.get("model_id"):
            call["model_id"] = data.get("model_id")
        if data.get("model_name"):
            call["model_name"] = data.get("model_name")
    if event_type == "call_failed" and call is not None:
        call["status"] = "failed"
        call["ended_at"] = event_at
        call["error"] = message or data.get("error")
        if isinstance(data.get("billing"), dict):
            call["billing"] = data.get("billing")
        if isinstance(data.get("usage"), dict):
            call["usage"] = data.get("usage")
    state["seq"] += 1
    state["updated_at"] = event_at
    calls = state.get("calls") or []
    billing_summary = state.get("billing_summary_override") or _build_billing_summary(calls)
    is_delta_event = bool(delta)
    event = {
        "type": event_type,
        "task_id": task_id,
        "seq": state["seq"],
        "delta": delta,
        "message": message,
        "stage": state.get("stage") or "",
        "status": state.get("status") or "running",
        "input_text": "" if is_delta_event else state.get("input_text") or "",
        "output_text": "" if is_delta_event else state.get("output_text") or "",
        "reasoning_text": "" if is_delta_event else state.get("reasoning_text") or "",
        "text": "" if is_delta_event else state.get("output_text") or "",
        "calls": [] if is_delta_event else calls,
        "billing_summary": billing_summary,
        "updated_at": state["updated_at"],
        "data": data,
    }
    events = state.setdefault("events", [])
    events.append(event)
    if len(events) > MAX_STREAM_EVENTS:
        del events[: len(events) - MAX_STREAM_EVENTS]
    for queue in list(state.get("subscribers") or []):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
    return event


def finish_ai_task_stream(task_id: int, *, status: str, message: str = "") -> None:
    publish_ai_task_event(task_id, "done", message=message, status=status)


async def subscribe_ai_task_stream(task_id: int):
    state = _get_stream(task_id)
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
    state.setdefault("subscribers", set()).add(queue)
    try:
        snapshot = get_ai_task_stream_snapshot(task_id)
        yield snapshot
        snapshot_seq = snapshot.get("seq") or 0
        for event in state.get("events") or []:
            if (event.get("seq") or 0) > snapshot_seq:
                yield event
        while True:
            event = await queue.get()
            yield event
            if event.get("type") == "done":
                return
    finally:
        subscribers = state.get("subscribers")
        if subscribers is not None:
            subscribers.discard(queue)
