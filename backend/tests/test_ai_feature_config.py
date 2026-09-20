import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.test_workbench_audit import build_change_details, soft_delete_workbench_record


def test_model_management_no_longer_uses_feature_assignment():
    model_source = (ROOT / "models" / "ai_models.py").read_text(encoding="utf-8")
    service_source = (ROOT / "services" / "ai_model_service.py").read_text(encoding="utf-8")
    page_source = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")
    detail_source = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "components" / "AiModelDetailDialog.vue").read_text(encoding="utf-8")

    assert "features:" not in model_source
    assert "AI_FEATURE_ALIASES" not in service_source
    assert "功能分配" not in page_source
    assert "功能分配" not in detail_source


def test_personal_model_weight_configuration_is_removed():
    from schemas import ai_schemas

    assert not hasattr(ai_schemas, "AiModelWeightRequest")


def test_quota_retry_response_contains_scope_and_model_name():
    service_source = (ROOT / "services" / "ai_service" / "__init__.py").read_text(encoding="utf-8")
    stream_source = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "_ai_stream.py").read_text(encoding="utf-8")

    assert '"quota_exhausted": True' in service_source
    assert '"current_model_scope": model_scope' in service_source
    assert '"current_model_name": model_name' in service_source
    assert '"scope": str(item.get("scope") or "platform")' in stream_source


def test_model_edit_dialog_uses_compact_two_column_layout():
    model_file = ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue"
    source = model_file.read_text(encoding="utf-8")

    assert 'class="model-dialog"' in source
    assert 'class="model-form-layout"' in source
    assert 'class="model-form-column"' in source
    assert '.model-dialog :deep(.el-dialog__body)' in source


def test_model_management_exposes_connectivity_and_reasoning_capabilities():
    model_file = ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue"
    source = model_file.read_text(encoding="utf-8")

    assert "连通性" in source
    assert "思考模式" in source
    assert "未检测，仅供配置参考" in source
    assert "connectivityVerified" in source


def test_connectivity_detection_does_not_gate_model_enablement():
    """能力检测仅用于辅助展示，不阻止模型启用。"""
    source = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")

    def body_of(func_name: str) -> str:
        start = source.index(f"function {func_name}(")
        nxt = source.find("\nasync function ", start + 1)
        alt = source.find("\nfunction ", start + 1)
        end = min(x for x in (nxt, alt, len(source)) if x != -1)
        return source[start:end]

    toggle = body_of("toggleEnabled")
    assert "requireConnectivity" not in toggle
    assert "await updateAiModel(row.id, { enabled: val })" in toggle

    assert "功能分配" not in source
    assert "能力检测用于辅助检查配置，不影响模型启用" in source


def test_ai_model_keeps_capability_fields_while_conversation_is_not_persisted():
    """模型能力字段仍需落库；AI 追问的对话过程则一律不落库。

    2026-07-27 无状态化改造：tw_requirement_ai_sessions / tw_requirement_ai_messages
    两张表已删除，平台只保存最终成果（补全需求 CREQ / 合并需求 MREQ）。
    思考过程改为随流式事件透传，不再有持久化字段。
    """
    model_file = ROOT / "models" / "ai_models.py"

    model_source = model_file.read_text(encoding="utf-8")
    assert "connectivity_status" in model_source
    assert "reasoning_status" in model_source

    workbench_models = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "models").glob("models_*.py")))
    assert "class TWRequirementAiSession" not in workbench_models
    assert "class TWRequirementAiMessage" not in workbench_models

    # 思考过程仍要能透传给前端，只是不入库
    assert "reasoning_content" in "".join(
        part.read_text(encoding="utf-8")
        for part in (ROOT / "services" / "requirement_ai_service").glob("*.py")
    )


def test_ai_call_uses_only_the_selected_model_and_records_after_model_returns():
    quota_file = ROOT / "services" / "ai_quota_service.py"
    service = "".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "services" / "ai_service").glob("*.py")
    )
    quota = quota_file.read_text(encoding="utf-8")

    assert "request_models = [model]" in service
    assert "_log_ai_usage_immediate" in service
    assert "reserve_ai_quota_slot" not in service
    # 调用日志现在保留成功、失败和未知状态，用于展示失败原因与重试记录。
    assert "AiUsageLog.status" in quota


def test_requirement_ai_result_validation_and_usage_result_filter_share_backend_rules():
    service = (ROOT / "services" / "ai_service" / "__init__.py").read_text(encoding="utf-8")
    refine = (ROOT / "services" / "requirement_ai_service" / "refine.py").read_text(encoding="utf-8")
    quota = (ROOT / "services" / "ai_quota_service.py").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")
    page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiUsage.vue").read_text(encoding="utf-8")
    filter_util = (ROOT.parent / "frontend" / "src" / "utils" / "aiUsageFilters.js").read_text(encoding="utf-8")

    assert "required_any_keys" in service
    assert "required_any_keys=recognized_keys" in refine
    assert "usage_result_filter_condition" in quota
    assert "result: str | None = Query" in endpoint
    assert "result=result" in endpoint
    assert 'label="结果"' in page
    assert "params.result = normalizedResult" in filter_util


def test_model_list_fetch_keeps_root_compatibility_and_falls_back_to_v1():
    from api.v1.endpoints.ai import _model_list_urls

    assert _model_list_urls("https://relay.example.com/") == [
        "https://relay.example.com/models",
        "https://relay.example.com/v1/models",
    ]
    assert _model_list_urls("https://relay.example.com/v1") == [
        "https://relay.example.com/v1/models",
    ]


@pytest.mark.asyncio
async def test_ai_call_records_usage_when_model_response_fails_validation(monkeypatch):
    from services import ai_service

    recorded = []

    async def record(**kwargs):
        recorded.append(kwargs)

    async def response_validation_failed(*_args, **_kwargs):
        raise ai_service._AiResponseValidationError(
            message="AI 返回内容无法解析为 JSON，请重试",
            metadata={"model": "claude-opus-4-8", "model_id": 5, "usage": {"total_tokens": 321}},
        )

    monkeypatch.setattr(ai_service, "_log_ai_usage_immediate", record)
    monkeypatch.setattr(ai_service, "_call_ai_for_feature", response_validation_failed)

    with pytest.raises(ai_service.UnifiedException):
        await ai_service.call_ai_for_feature(
            db=None,
            current_user=SimpleNamespace(id=1, is_superuser=False),
            feature="test_workbench_test_case",
            system_prompt="system",
            user_content="user",
        )

    assert len(recorded) == 1
    log = recorded[0]
    assert {
        "user_id": log["user_id"],
        "action": log["action"],
        "model": log["model"],
        "model_id": log["model_id"],
        "tokens_estimated": log["tokens_estimated"],
    } == {
        "user_id": 1,
        "action": "ai_call",
        "model": "claude-opus-4-8",
        "model_id": 5,
        "tokens_estimated": 321,
    }
    assert log["status"] == "failed"
    assert log["failure_reason"] == "模型已返回内容，但结果解析或校验失败"
    assert log["quota_consumed"] is True


def test_model_output_reference_has_current_cloud_and_local_presets():
    model_page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")

    for preset in (
        "GPT-5.6（Sol）",
        "Claude Opus 5",
        "Gemini 3.1 Pro",
        "DeepSeek V4（Pro / Flash）",
        "Qwen3 / Qwen3-Coder（32K 上下文）",
        "Llama 3.3 / Gemma 3（32K 上下文）",
    ):
        assert preset in model_page


def test_stream_error_body_is_read_before_being_reported():
    """流式 4xx 必须先 aread() 再取 .text，否则 httpx.ResponseNotRead 会掩盖上游真实报错。"""
    import httpx

    from llm.providers import _safe_response_text

    providers = (ROOT / "llm" / "providers" / "openai_compat.py").read_text(encoding="utf-8")
    stream_body = providers[providers.index("async def _chat_with_meta_stream"):]

    # 错误体读取发生在 raise_for_status 之前（即仍在 client.stream 上下文内）
    assert "await response.aread()" in stream_body
    assert stream_body.index("await response.aread()") < stream_body.index("response.raise_for_status()")
    # 两条 HTTP 错误分支都不再裸取 .text
    assert "exc.response.text" not in providers

    # 未读的流式响应取 .text 会抛 ResponseNotRead，_safe_response_text 必须兜住而不是把它抛出去
    with pytest.raises(httpx.ResponseNotRead):
        httpx.Response(400, stream=httpx.AsyncByteStream()).text
    assert _safe_response_text(httpx.Response(400, stream=httpx.AsyncByteStream())) == "(上游未返回可读的错误内容)"
    # 已读（或非流式）响应正常回显上游报文
    assert _safe_response_text(httpx.Response(400, content=b'{"error":"bad request"}')) == '{"error":"bad request"}'
    assert _safe_response_text(None) == ""


def test_broken_llm_json_is_repaired_instead_of_discarded():
    """模型偶发吐出非法 JSON（漏逗号/未转义引号等）时，用 json-repair 兜底而不是整份作废。"""
    ai_service = "".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "services" / "ai_service").glob("*.py")
    )

    # 引入 json-repair，且缺库时优雅降级（不因 ImportError 影响启动）
    assert "from json_repair import repair_json" in ai_service
    assert "_json_repair = None" in ai_service
    # json-repair 作为最后兜底：位于手写策略链之后（在 return None 之前），
    # 因为手写策略对 Qwen 中文引号终止符等领域特例更精准，不能被 json-repair 抢先。
    assert "_json_repair(" in ai_service
    body = ai_service[ai_service.index("def _robust_json_parse"): ai_service.index("def _parse_json_with_log")]
    assert body.index('s.find("{")') < body.index("_json_repair(")
    assert body.rindex("_json_repair(") < body.rindex("return None")

    # 依赖已声明
    reqs = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "json-repair" in reqs

    # 功能验证：json-repair 能修复今天这类 "Expecting ',' delimiter"
    try:
        from json_repair import repair_json
    except Exception:
        pytest.skip("json-repair 未安装，跳过功能验证")
    bad = '{"options":["A"\n"B"],"ready":false}'  # 数组元素间漏逗号
    with pytest.raises(json.JSONDecodeError):
        json.loads(bad)
    fixed = repair_json(bad, return_objects=True)
    assert isinstance(fixed, dict) and fixed.get("options") == ["A", "B"]


def test_json_mode_is_requested_with_capability_probe_and_one_shot_fallback():
    """结构化调用请求 response_format 强制 JSON；网关不支持时一次性降级并缓存，非通用重试。"""
    from llm.providers import _response_format_rejected, _JSON_MODE_UNSUPPORTED

    providers = (ROOT / "llm" / "providers" / "openai_compat.py").read_text(encoding="utf-8")
    ai_service = "".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "services" / "ai_service").glob("*.py")
    )

    # payload 构造：openai-compat + json_mode + 未被标记不支持时才附带 response_format
    assert "json_mode: bool = False" in providers
    assert '"response_format"] = {"type": "json_object"}' in providers
    assert "_JSON_MODE_UNSUPPORTED" in providers

    # 两个 chat 方法都要在网关拒绝 response_format 时一次性降级并缓存
    for marker in ("async def _chat_with_meta(", "async def _chat_with_meta_stream("):
        method = providers[providers.index(marker):]
        method = method[: method.find("\n    async def ", 1) if method.find("\n    async def ", 1) > 0 else len(method)]
        assert "_response_format_rejected(status, body)" in method
        assert "_JSON_MODE_UNSUPPORTED.add((self.base_url, self.model))" in method
        assert "json_mode=False" in method

    # 结构化调用（非 raw_mode）才开 JSON 模式
    assert "want_json_mode = not raw_mode" in ai_service
    assert "json_mode=want_json_mode" in ai_service

    # 判定函数只认 response_format / json_object 字样，不误伤无关业务错误（如 503 无可用渠道）
    assert _response_format_rejected(400, '{"error":"response_format is not supported"}') is True
    assert _response_format_rejected(400, "unknown field json_object") is True
    assert _response_format_rejected(503, "当前分组 default 下对于模型 X 无可用渠道") is False
    assert _response_format_rejected(200, "ok") is False
    assert isinstance(_JSON_MODE_UNSUPPORTED, set)
