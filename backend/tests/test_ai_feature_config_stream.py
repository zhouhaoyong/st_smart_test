import ast
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.test_workbench_audit import build_change_details, soft_delete_workbench_record
from api.v1.endpoints.test_workbench_routers._ai_stream import (
    AI_STREAM_HEARTBEAT_SECONDS,
    stream_ai_call,
)
from core.response import UnifiedException


def _literal_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"未找到配置项：{name}")


def test_requirement_ai_stream_never_writes_inside_the_stream_and_renders_failures_in_chat():
    """流式端点内不得写业务数据。

    历史故障（2026-07-27）：会话状态写在流式响应体内部的 on_success 里提交，
    事务随请求会话被回收而丢失，表现为追问空转、多轮回复逐字相同。
    因此：首轮的 initial_content 必须在 return StreamingResponse 之前提交，
    而 on_success 里只允许 rollback。
    """
    requirement_endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py").read_text(encoding="utf-8")
    stream_helper = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "_ai_stream.py").read_text(encoding="utf-8")
    composable = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "composables" / "useRequirementRefinement.js").read_text(encoding="utf-8")

    start = requirement_endpoint.index("async def ask_requirement_ai_stream")
    end = requirement_endpoint.index("async def compose_requirement_ai_stream", start)
    ask_stream = requirement_endpoint[start:end]

    # initial_content 在流式响应开始前落库
    assert "await db.commit()" in ask_stream
    assert ask_stream.index("await db.commit()") < ask_stream.index("async def call(emit):")
    # 流式响应体内只回滚、不提交
    success_body = ask_stream[ask_stream.index("async def on_success(result):"):]
    assert "await db.rollback()" in success_body
    assert "await db.commit()" not in success_body
    assert "logger.exception" in stream_helper
    assert "formatConversationError" in composable
    assert "ElMessage.error(err?.message || 'AI 补全失败')" not in composable
    assert "ElMessage.error(err?.message || 'AI 整理需求正文失败')" not in composable


def test_user_messages_remain_copyable_while_the_next_ai_reply_is_generating():
    composable = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "composables" / "useRequirementRefinement.js").read_text(encoding="utf-8")

    assert "const messageCopyable = message =>" in composable
    assert "if (message.role === 'user') return true" in composable
    assert "return !message.pending" in composable


def test_ai_failures_stay_in_the_chat_instead_of_falling_back_to_the_start_page():
    """模型报错以 AI 气泡展示：首轮失败不得退回「开始 AI 补全」确认页。"""
    drawer = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementRefinementDrawer.vue").read_text(encoding="utf-8")
    card = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RefinementMessageCard.vue").read_text(encoding="utf-8")
    composable = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "composables" / "useRequirementRefinement.js").read_text(encoding="utf-8")

    assert 'v-if="!conversationStarted"' in drawer
    assert 'v-if="!session && !streaming"' not in drawer
    assert 'v-if="!conversationBroken && workflow.actionHint"' in drawer
    assert "conversationStarted.value = true" in composable
    assert "conversationBroken.value = true" in composable
    assert "errorHint" in composable and "管理中心" in composable
    assert 'v-if="message.error" class="error-actions"' in card
    assert 'const hasRetryAction = computed(() => !!props.message.retryAction)' in card


def test_ai_stream_sends_heartbeat_and_keeps_unified_result_payload():
    async def scenario():
        async def call(_emit):
            await asyncio.sleep(0.225)
            return {
                "code": 200,
                "message": "分析完成",
                "data": {"preview_id": "preview-1"},
            }

        chunks = []
        async for chunk in stream_ai_call(
            call,
            heartbeat_seconds=0.1,
            unwrap_unified_response=True,
        ):
            chunks.append(json.loads(chunk))
        return chunks

    events = asyncio.run(scenario())

    heartbeat_events = [
        event["type"] == "event"
        and event["data"]["type"] == "heartbeat"
        for event in events
    ]
    assert sum(heartbeat_events) >= 2
    assert events[-1] == {
        "type": "complete",
        "code": 200,
        "message": "分析完成",
        "data": {"preview_id": "preview-1"},
    }


def test_ai_stream_keeps_safe_error_data_for_long_ai_requests():
    async def scenario():
        async def call(_emit):
            raise UnifiedException(
                code=500,
                message="AI分析失败",
                data={"recommend_summary": {"usage": {"total_tokens": 1}}},
            )

        chunks = []
        async for chunk in stream_ai_call(call, include_error_data=True):
            chunks.append(json.loads(chunk))
        return chunks

    events = asyncio.run(scenario())

    assert events[-1]["type"] == "error"
    assert events[-1]["data"] == {
        "recommend_summary": {"usage": {"total_tokens": 1}}
    }


def test_ai_stream_cancels_the_underlying_call_when_client_stops_reading():
    async def scenario():
        canceled = False

        async def call(_emit):
            nonlocal canceled
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                canceled = True
                raise

        stream = stream_ai_call(call)
        await anext(stream)
        await asyncio.sleep(0)
        await stream.aclose()
        return canceled

    assert asyncio.run(scenario()) is True


def test_interface_case_generation_long_routes_use_streaming():
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "import_ai.py").read_text(encoding="utf-8")

    assert AI_STREAM_HEARTBEAT_SECONDS == 30.0
    assert '@router.post("/generate/stream")' in endpoint
    assert "stream_ai_call(" in endpoint


def test_interface_case_generation_imports_the_prompt_loader_used_by_generation():
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "import_ai.py").read_text(encoding="utf-8")

    assert "from utils.prompt_loader import load_prompt" in endpoint
