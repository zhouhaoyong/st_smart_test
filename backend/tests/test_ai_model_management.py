from pathlib import Path
import sys
import asyncio
import importlib.util
import json
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import ai_models
from services import ai_model_service
from services import ai_billing_service
from services import ai_quota_service


class _DetachedLookupSession:
    def expunge(self, _model):
        pass


class _AsyncLookupSession:
    async def __aenter__(self):
        return _DetachedLookupSession()

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False


def _eligible_model(model_id: int, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=model_id,
        name=name,
        model=f"model-{model_id}",
        scope="platform",
        enabled=True,
        invalidated_reason=None,
        connectivity_status="passed",
        max_output_tokens=None,
    )


def _patch_ai_service_candidates(monkeypatch, models, provider_by_model_id, *, quota_scope="platform"):
    from services import ai_service

    async def get_candidates(_db, _feature, **_kwargs):
        return models

    async def get_provider(model):
        return provider_by_model_id[model.id]

    async def check_quota(_user, _model):
        return quota_scope

    async def no_op_log(**_kwargs):
        return None

    monkeypatch.setattr(ai_service, "AsyncSessionLocal", _AsyncLookupSession)
    monkeypatch.setattr(ai_service, "get_candidate_models_for_feature", get_candidates)
    monkeypatch.setattr(ai_service, "get_provider_for_model", get_provider)
    monkeypatch.setattr(ai_service, "_ensure_ai_quota_available_immediate", check_quota)
    monkeypatch.setattr(ai_service, "_log_ai_usage_immediate", no_op_log)
    return ai_service


class _FlushSession:
    async def flush(self):
        pass


def test_status_only_enable_does_not_require_capability_check():
    model = SimpleNamespace(
        id=11,
        enabled=False,
        connectivity_status="unknown",
        base_url="https://example.com",
        model="demo-model",
        provider="openai-compat",
        api_key_encrypted=None,
        reasoning_status="unknown",
        reasoning_checked_at=None,
        reasoning_profile="chat_template",
        usage_status="unknown",
        usage_checked_at=None,
    )

    asyncio.run(ai_model_service.update_model(_FlushSession(), model, {"enabled": True}))

    assert model.enabled is True


def test_update_model_can_clear_stale_usage_status_to_unknown():
    model = SimpleNamespace(
        id=12,
        enabled=True,
        connectivity_status="passed",
        base_url="https://example.com",
        model="demo-model",
        provider="openai-compat",
        api_key_encrypted=None,
        reasoning_status="supported",
        reasoning_checked_at=None,
        reasoning_profile="none",
        usage_status="supported",
        usage_checked_at="2026-09-03T10:00:00+08:00",
    )

    asyncio.run(ai_model_service.update_model(_FlushSession(), model, {"usage_status": "unknown"}))

    assert model.usage_status == "unknown"
    assert model.usage_checked_at is None


def test_update_model_can_clear_max_output_tokens():
    model = SimpleNamespace(
        id=13,
        enabled=True,
        connectivity_status="passed",
        base_url="https://example.com",
        model="demo-model",
        provider="openai-compat",
        api_key_encrypted=None,
        max_output_tokens=8192,
        reasoning_status="unknown",
        reasoning_checked_at=None,
        reasoning_profile="chat_template",
        usage_status="unknown",
        usage_checked_at=None,
    )

    asyncio.run(ai_model_service.update_model(_FlushSession(), model, {"max_output_tokens": None}))

    assert model.max_output_tokens is None


def test_responses_payload_extracts_assistant_text_when_output_text_is_missing():
    from llm.providers.openai_compat import _extract_responses_output_text

    payload = {
        "status": "completed",
        "output": [
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "不应混入最终结果"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": '{"interfaces": []}'},
                ],
            },
        ],
    }

    assert _extract_responses_output_text(payload) == '{"interfaces": []}'


def test_temporary_model_selection_only_calls_requested_model_and_reuses_group(monkeypatch):
    first = _eligible_model(1, "模型一")
    second = _eligible_model(2, "模型二")
    calls = []

    class Provider:
        async def _chat_with_meta(self, *_args, **_kwargs):
            calls.append(self.model_id)
            return {"content": "原始内容", "usage": {"total_tokens": 3}}

        def __init__(self, model_id):
            self.model_id = model_id
            self.model = f"provider-{model_id}"

    ai_service = _patch_ai_service_candidates(
        monkeypatch,
        [first, second],
        {1: Provider(1), 2: Provider(2)},
    )
    events = []

    async def emit(event):
        events.append(event)

    _result, metadata = asyncio.run(ai_service._call_ai_for_feature(
        None,
        SimpleNamespace(id=7, is_superuser=False),
        feature="test_workbench_requirement_completion",
        system_prompt="系统提示",
        user_content="用户内容",
        raw_mode=True,
        return_metadata=True,
        selected_model_id=2,
        call_group_id="retry-group-1",
        stream_callback=emit,
    ))

    assert calls == [2]
    assert metadata["call_group_id"] == "retry-group-1"
    assert any(
        event["type"] == "call_start" and event["call_group_id"] == "retry-group-1"
        for event in events
    )


def test_temporary_model_selection_rejects_model_outside_user_candidates(monkeypatch):
    model = _eligible_model(1, "可用模型")
    ai_service = _patch_ai_service_candidates(monkeypatch, [model], {1: SimpleNamespace()})

    with pytest.raises(Exception, match="所选模型当前不可用"):
        asyncio.run(ai_service._call_ai_for_feature(
            None,
            SimpleNamespace(id=7, is_superuser=False),
            feature="test_workbench_requirement_completion",
            system_prompt="系统提示",
            user_content="用户内容",
            raw_mode=True,
            selected_model_id=9,
        ))


def test_failed_temporary_model_call_exposes_retry_candidates_without_auto_retry(monkeypatch):
    first = _eligible_model(1, "首选模型")
    second = _eligible_model(2, "备用模型")
    second.scope = "personal"
    calls = []

    class FailingProvider:
        model = "provider-1"

        async def _chat_with_meta(self, *_args, **_kwargs):
            calls.append(1)
            raise RuntimeError("LLM API HTTP error: 503 temporary upstream failure")

    class UnusedProvider:
        model = "provider-2"

        async def _chat_with_meta(self, *_args, **_kwargs):
            calls.append(2)
            return {"content": "不应调用", "usage": {}}

    ai_service = _patch_ai_service_candidates(
        monkeypatch,
        [first, second],
        {1: FailingProvider(), 2: UnusedProvider()},
    )
    events = []

    async def emit(event):
        events.append(event)

    with pytest.raises(Exception) as error:
        asyncio.run(ai_service._call_ai_for_feature(
            None,
            SimpleNamespace(id=7, is_superuser=False),
            feature="test_workbench_requirement_completion",
            system_prompt="系统提示",
            user_content="用户内容",
            raw_mode=True,
            selected_model_id=1,
            call_group_id="retry-group-2",
            stream_callback=emit,
        ))

    assert calls == [1]
    assert error.value.data["call_group_id"] == "retry-group-2"
    assert error.value.data["platform_model_unavailable"] is True
    assert "平台模型暂时无法使用：上游服务暂时不可用（503）" in str(error.value)
    assert "设置使用权重" not in str(error.value)
    assert "选择模型重试" in str(error.value)
    assert "上游服务暂时不可用（503）" in error.value.data["failure_reason"]
    assert error.value.data["retry_candidates"] == [{"id": 2, "name": "备用模型", "model": "model-2", "scope": "personal"}]
    failed_event = next(event for event in events if event["type"] == "call_failed")
    assert failed_event["call_group_id"] == "retry-group-2"
    assert failed_event["platform_model_unavailable"] is True
    assert failed_event["retry_candidates"] == [{"id": 2, "name": "备用模型", "model": "model-2", "scope": "personal"}]


def test_workbench_ai_request_schemas_accept_temporary_model_selection_and_retry_group():
    from schemas.test_workbench import (
        TWMergeAiAsk,
        TWMergeAiCompare,
        TWMergeAiCompose,
        TWRequirementAiAsk,
        TWRequirementAiCompare,
        TWRequirementAiCompose,
        TWTestCaseGenerateRequest,
        TWTestCasePreflightAsk,
    )

    platform = {"selected_model_id": 2, "call_group_id": "retry-group-3"}
    requests = [
        TWRequirementAiAsk(**platform),
        TWRequirementAiCompose(**platform),
        TWRequirementAiCompare(markdown_content="正文", **platform),
        TWMergeAiAsk(version_id=1, source_type="requirement", source_ids=[1], **platform),
        TWMergeAiCompose(version_id=1, source_type="requirement", source_ids=[1], **platform),
        TWMergeAiCompare(version_id=1, source_type="requirement", source_ids=[1], markdown_content="正文", **platform),
        TWTestCasePreflightAsk(project_id=1, source_type="requirement", source_ids=[1], **platform),
        TWTestCaseGenerateRequest(project_id=1, source_type="requirement", source_ids=[1], **platform),
    ]

    assert all(item.selected_model_id == 2 for item in requests)
    assert all(item.call_group_id == "retry-group-3" for item in requests)


def test_compose_continuation_forwards_the_same_temporary_model_and_call_group(monkeypatch):
    from services import requirement_ai_service

    calls = []

    async def fake_call_ai_for_feature(*_args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {"raw": "原始需求"}, {
                "model_id": 2,
                "model": "模型二",
                "usage": {},
                "finish_reason": "length",
                "call_group_id": kwargs["call_group_id"],
            }
        return {"raw": "续写内容"}, {
            "model_id": 2,
            "model": "模型二",
            "usage": {},
            "finish_reason": "stop",
            "call_group_id": kwargs["call_group_id"],
        }

    async def no_op_capability(*_args, **_kwargs):
        return None

    monkeypatch.setattr(requirement_ai_service.synthesize, "call_ai_for_feature", fake_call_ai_for_feature)
    monkeypatch.setattr(requirement_ai_service.synthesize, "_upgrade_model_capability", no_op_capability)

    result = asyncio.run(requirement_ai_service.compose_requirement_markdown(
        None,
        SimpleNamespace(id=7, is_superuser=False),
        SimpleNamespace(id=1, title="需求", original_content="原始需求", markdown_content=""),
        history=[{"text": "问题", "status": "answered", "answer": "答案"}],
        selected_model_id=2,
        call_group_id="retry-group-4",
    ))

    assert result["call_group_id"] == "retry-group-4"
    assert len(calls) == 2
    assert all(call["selected_model_id"] == 2 for call in calls)
    assert all(call["call_group_id"] == "retry-group-4" for call in calls)


def test_test_workbench_ai_routes_forward_temporary_selection_and_remove_early_platform_quota_guard():
    route_sources = {
        "requirements": (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py").read_text(encoding="utf-8"),
        "merged_ai": (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "merged_ai.py").read_text(encoding="utf-8"),
        "test_cases": (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8"),
        "merged": (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "merged.py").read_text(encoding="utf-8"),
    }

    for source in (route_sources["requirements"], route_sources["merged_ai"], route_sources["test_cases"]):
        assert "selected_model_id=data.selected_model_id" in source
        assert "call_group_id=data.call_group_id" in source

    assert "check_user_ai_quota" not in route_sources["test_cases"]
    assert "selected_model_id=selected_model_id" in route_sources["merged"]
    assert "call_group_id=call_group_id" in route_sources["merged"]


def test_stream_error_exposes_only_safe_retry_metadata():
    from core.response import UnifiedException
    module_path = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "_ai_stream.py"
    module_spec = importlib.util.spec_from_file_location("test_workbench_ai_stream", module_path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    stream_requirement_ai_call = module.stream_requirement_ai_call

    async def call(_emit):
        raise UnifiedException(
            code=400,
            message="AI调用失败：上游服务暂时不可用（503）",
            data={
                "call_group_id": "retry-group-5",
                "failure_reason": "上游服务暂时不可用（503）",
                "retry_candidates": [{"id": 2, "name": "备用模型", "model": "model-2"}],
                "model_error": "不应暴露的原始上游信息",
            },
        )

    async def on_success(_result):
        return None

    async def collect():
        return [json.loads(chunk) async for chunk in stream_requirement_ai_call(call, on_success)]

    payloads = asyncio.run(collect())
    error = next(item for item in payloads if item["type"] == "error")

    assert error["call_group_id"] == "retry-group-5"
    assert error["failure_reason"] == "上游服务暂时不可用（503）"
    assert error["retry_candidates"] == [{"id": 2, "name": "备用模型", "model": "model-2", "scope": "platform"}]
    assert "model_error" not in error


def test_confirmed_retry_writes_separate_usage_logs_with_the_same_group(monkeypatch):
    model = _eligible_model(1, "模型一")
    logs = []

    class Provider:
        model = "provider-1"

        async def _chat_with_meta(self, *_args, **_kwargs):
            return {"content": "原始内容", "usage": {"total_tokens": 2}}

    ai_service = _patch_ai_service_candidates(monkeypatch, [model], {1: Provider()})

    async def capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(ai_service, "_log_ai_usage_immediate", capture_log)
    user = SimpleNamespace(id=7, is_superuser=False)
    for _ in range(2):
        asyncio.run(ai_service.call_ai_for_feature(
            None,
            user,
            feature="test_workbench_requirement_completion",
            system_prompt="系统提示",
            user_content="用户内容",
            raw_mode=True,
            selected_model_id=1,
            call_group_id="retry-group-6",
        ))

    assert len(logs) == 2
    assert all(item["call_group_id"] == "retry-group-6" for item in logs)
    assert all(item["model_id"] == 1 for item in logs)


def test_model_management_removes_user_model_weights():
    assert "scope" in ai_models.AiModel.__table__.columns
    assert "invalidated_reason" in ai_models.AiModel.__table__.columns
    assert not hasattr(ai_models, "AiUserModelWeight")


def test_model_management_hides_weight_controls_and_endpoint():
    source = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")

    assert 'label="使用权重"' not in source
    assert "使用权重" not in source
    assert "weightValue" not in source
    assert "setAiModelWeight" not in source
    assert 'label="接口地址" prop="base_url"' not in source
    assert "模型优先级" in source


def test_platform_model_terminology_replaces_platform_scope_in_runtime_and_storage():
    models = (ROOT / "models" / "ai_models.py").read_text(encoding="utf-8")
    quota_service = (ROOT / "services" / "ai_quota_service.py").read_text(encoding="utf-8")

    assert '__tablename__ = "ai_platform_quota_settings"' in models
    assert 'scope == "platform"' in quota_service
    assert 'return allowed, used, limit, message, "platform"' in quota_service


def test_user_routing_uses_enabled_platform_then_owned_personal_models_without_detection_gate():
    sorter = getattr(ai_model_service, "sort_models_for_user_feature", None)
    assert callable(sorter)

    user = SimpleNamespace(id=7, is_superuser=False)
    models = [
        SimpleNamespace(id=8, scope="platform", owner_user_id=1, enabled=True, invalidated_reason=None,
                        connectivity_status="unknown"),
        SimpleNamespace(id=2, scope="personal", owner_user_id=7, enabled=True, invalidated_reason=None,
                        connectivity_status="failed"),
        SimpleNamespace(id=3, scope="personal", owner_user_id=8, enabled=True, invalidated_reason=None,
                        connectivity_status="unknown"),
        SimpleNamespace(id=1, scope="platform", owner_user_id=1, enabled=False, invalidated_reason=None,
                        connectivity_status="unknown"),
    ]

    result = sorter(
        user,
        models,
        "test_workbench_requirement_completion",
    )

    assert [model.id for model in result] == [8, 2]


def test_model_page_no_longer_exposes_global_default_model_controls():
    source = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")

    assert "设为默认" not in source
    assert "默认模型" not in source


def test_ai_usage_source_is_removed_from_storage_and_api_contract():
    model_source = (ROOT / "models" / "ai_models.py").read_text(encoding="utf-8")
    service_source = (ROOT / "services" / "ai_quota_service.py").read_text(encoding="utf-8")
    endpoint_source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")
    writer_source = (ROOT / "services" / "ai_service" / "__init__.py").read_text(encoding="utf-8")

    assert "source: Mapped" not in model_source
    assert "AiUsageLog.source" not in service_source
    assert '"source": log.source' not in service_source
    assert "source: str | None" not in service_source
    assert 'source="manual"' not in writer_source
    assert 'source: str | None = Query' not in endpoint_source


def test_superuser_downgrade_invalidates_owned_platform_models():
    endpoint_source = (ROOT / "api" / "v1" / "endpoints" / "users.py").read_text(encoding="utf-8")
    service_source = (ROOT / "services" / "ai_model_service.py").read_text(encoding="utf-8")

    assert "invalidate_owner_platform_models" in endpoint_source
    assert "原超管权限已取消" in service_source


def test_model_scope_cannot_be_changed_after_creation():
    source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")

    update_endpoint = source[source.index("async def api_update_model"):source.index('@router.post("/models/{model_id}/test-billing")')]
    assert "模型范围创建后不可修改" in update_endpoint


def test_reusable_readonly_model_detail_dialog_respects_viewer_scope():
    component = ROOT.parent / "frontend" / "src" / "views" / "admin" / "components" / "AiModelDetailDialog.vue"
    page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")

    assert component.exists()
    source = component.read_text(encoding="utf-8")
    for text in ("viewerMode", "member", "superadmin", "owner", "base_url"):
        assert text in source
    assert "我的权重" not in source
    assert "feature_weights" not in source
    for sensitive in ("balance_query_config", "api_key_masked", "headers"):
        assert sensitive not in source
    assert "AiModelDetailDialog" in page
    assert "openDetail" in page


def test_workbench_model_selection_and_confirmed_retry_use_shared_payload():
    frontend = ROOT.parent / "frontend" / "src" / "views" / "test-workbench"
    start_confirm = (frontend / "components" / "RefinementStartConfirm.vue").read_text(encoding="utf-8")
    refinement = (frontend / "composables" / "useRequirementRefinement.js").read_text(encoding="utf-8")
    test_case_dialog = (frontend / "components" / "TestCaseGenerateDialog.vue").read_text(encoding="utf-8")

    for marker in ("modelCandidates", "selectedModelId", "仅本次使用"):
        assert marker in start_confirm
    for marker in ("getAiModelsForFeature", "selected_model_id", "call_group_id", "retry_candidates"):
        assert marker in refinement
    assert "model-candidates" in test_case_dialog
