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


def test_model_failure_summary_does_not_expose_unclassified_provider_response():
    from services.ai_service import _summarize_model_attempt_error

    assert _summarize_model_attempt_error("provider response contains api_key=secret-value") == "模型服务返回异常"


def test_model_capability_error_is_desensitized_before_returning_to_user():
    module_path = ROOT / "api" / "v1" / "endpoints" / "ai.py"
    module_spec = importlib.util.spec_from_file_location("test_ai_endpoint", module_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec.loader is not None
    module_spec.loader.exec_module(module)

    detail = module._capability_error_detail(Exception("HTTP 401: api_key=secret-value"))

    assert detail == "模型认证失败，请检查 API Key"
    assert "secret-value" not in detail


def test_capability_quota_error_with_api_key_text_is_not_authentication_failure():
    from services.ai_capability_service import _capability_error_detail

    provider_error = (
        'HTTP 429: {"error":{"code":"insufficient_quota",'
        '"message":"API key 额度已用完"}}'
    )

    assert _capability_error_detail(Exception(provider_error)) == "模型服务余额或额度不足"


def test_unverified_model_can_be_created_enabled():
    source = (ROOT / "services" / "ai_model_service.py").read_text(encoding="utf-8")

    assert 'data["enabled"] = False' not in source


def test_failure_detail_keeps_provider_context_and_masks_credentials():
    from services.ai_service import _detailed_model_failure_reason

    detail = _detailed_model_failure_reason(
        "LLM API HTTP error: 429 insufficient_quota; Authorization: Bearer secret-value"
    )

    assert "模型服务余额或额度不足" in detail
    assert "429 insufficient_quota" in detail
    assert "secret-value" not in detail


def test_insufficient_quota_with_api_key_text_is_not_misclassified_as_authentication():
    from services.ai_service import _summarize_model_attempt_error

    provider_error = (
        'LLM API HTTP error: 429: '
        '{"error":{"code":"insufficient_quota","message":"API key 额度已用完"}}'
    )

    assert _summarize_model_attempt_error(provider_error) == "模型服务余额或额度不足"


def test_draft_capability_reuses_saved_api_key_for_edit(monkeypatch):
    module_path = ROOT / "api" / "v1" / "endpoints" / "ai.py"
    module_spec = importlib.util.spec_from_file_location("test_ai_endpoint_draft_key", module_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec.loader is not None
    module_spec.loader.exec_module(module)

    saved_model = SimpleNamespace(
        id=19,
        name="旧模型别名",
        provider="openai-compat",
        scope="personal",
        owner_user_id=7,
        created_by=7,
        base_url="https://old.example.com/v1",
        model="old-model",
        api_key_encrypted="encrypted-key",
        reasoning_status="unknown",
        reasoning_profile="chat_template",
        reasoning_checked_at=None,
        usage_status="unknown",
        usage_checked_at=None,
        connectivity_status="unknown",
        connectivity_checked_at=None,
    )
    current_user = SimpleNamespace(id=7, real_name="模型管理员", is_superuser=False)
    observed = {}

    async def fake_get_model(_db, model_id):
        assert model_id == saved_model.id
        return saved_model

    async def fake_probe(base_url, api_key, model_name, provider_type, *, cancel_check=None, **_kwargs):
        observed.update({
            "base_url": base_url,
            "api_key": api_key,
            "model_name": model_name,
            "provider_type": provider_type,
        })
        return {
            "supported": False,
            "profile": "",
            "preview": "",
            "has_usage": False,
            "usage": {},
        }

    class _Guard:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

    class _Db:
        def add(self, _item):
            pass

        async def commit(self):
            pass

    async def fake_log_operation(**_kwargs):
        pass

    monkeypatch.setattr(module, "get_model", fake_get_model)
    monkeypatch.setattr(module, "_can_manage_model", lambda _user, model: model.id == saved_model.id)
    monkeypatch.setattr(module, "resolve_model_api_key", lambda _model: "saved-secret-key")
    monkeypatch.setattr(module, "_probe_model_capabilities", fake_probe)
    monkeypatch.setattr(module, "_ai_model_concurrency_guard", lambda *_args: _Guard())
    monkeypatch.setattr(module, "log_operation", fake_log_operation)

    request = module.AiModelConnectivityRequest(
        model_id=saved_model.id,
        provider="openai-compat",
        base_url="https://new.example.com/v1",
        model="new-model",
    )
    assert request.model_id == saved_model.id

    result = asyncio.run(module.api_test_model_capabilities_draft(request, _Db(), current_user))

    assert result["code"] == 200
    assert observed == {
        "base_url": "https://new.example.com/v1",
        "api_key": "saved-secret-key",
        "model_name": "new-model",
        "provider_type": "openai-compat",
    }


def test_cancelled_capability_test_resets_saved_model_to_unverified(monkeypatch):
    module_path = ROOT / "api" / "v1" / "endpoints" / "ai.py"
    module_spec = importlib.util.spec_from_file_location("test_ai_endpoint_cancel", module_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec.loader is not None
    module_spec.loader.exec_module(module)

    saved_model = SimpleNamespace(
        id=31,
        name="待重置模型",
        connectivity_status="passed",
        connectivity_checked_at="2026-08-31T10:00:00+08:00",
        reasoning_status="supported",
        reasoning_checked_at="2026-08-31T10:00:00+08:00",
        usage_status="supported",
        usage_checked_at="2026-08-31T10:00:00+08:00",
    )
    current_user = SimpleNamespace(id=7, real_name="模型管理员", is_superuser=False)

    async def fake_get_model(_db, model_id):
        assert model_id == saved_model.id
        return saved_model

    class _Db:
        async def commit(self):
            pass

    async def fake_log_operation(**_kwargs):
        pass

    monkeypatch.setattr(module, "get_model", fake_get_model)
    monkeypatch.setattr(module, "_can_manage_model", lambda _user, model: model.id == saved_model.id)
    monkeypatch.setattr(module, "log_operation", fake_log_operation)

    result = asyncio.run(module.api_reset_model_capabilities(saved_model.id, _Db(), current_user))

    assert result["code"] == 200
    assert saved_model.connectivity_status == "unknown"
    assert saved_model.connectivity_checked_at is None
    assert saved_model.reasoning_status == "unknown"
    assert saved_model.reasoning_checked_at is None
    assert saved_model.usage_status == "unknown"
    assert saved_model.usage_checked_at is None


def test_timeout_interrupted_capability_test_is_audited_apart_from_manual_stop(monkeypatch):
    """前端等待超时的中断必须单独留痕，且与用户手动点终止区分开。"""
    module_path = ROOT / "api" / "v1" / "endpoints" / "ai.py"
    module_spec = importlib.util.spec_from_file_location("test_ai_endpoint_interrupt", module_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec.loader is not None
    module_spec.loader.exec_module(module)

    saved_model = SimpleNamespace(
        id=33,
        name="超时中断模型",
        connectivity_status="passed",
        connectivity_checked_at="2026-08-31T10:00:00+08:00",
        reasoning_status="supported",
        reasoning_checked_at="2026-08-31T10:00:00+08:00",
        usage_status="supported",
        usage_checked_at="2026-08-31T10:00:00+08:00",
    )
    current_user = SimpleNamespace(id=7, real_name="模型管理员", is_superuser=False)
    audited = []

    async def fake_get_model(_db, model_id):
        return saved_model

    class _Db:
        async def commit(self):
            pass

    async def fake_log_operation(**kwargs):
        audited.append(kwargs)

    monkeypatch.setattr(module, "get_model", fake_get_model)
    monkeypatch.setattr(module, "_can_manage_model", lambda _user, _model: True)
    monkeypatch.setattr(module, "log_operation", fake_log_operation)

    timeout_result = asyncio.run(
        module.api_reset_model_capabilities(saved_model.id, _Db(), current_user, reason="timeout")
    )
    manual_result = asyncio.run(
        module.api_reset_model_capabilities(saved_model.id, _Db(), current_user)
    )

    assert timeout_result["code"] == 200
    assert manual_result["code"] == 200
    # 操作类型统一为「模型能力检测」，中断与终止靠操作内容区分。
    assert audited[0]["operation"] == "模型能力检测"
    assert audited[0]["description"] == "模型能力检测中断：超时中断模型"
    assert audited[1]["operation"] == "模型能力检测"
    assert audited[1]["description"] == "模型能力检测终止：超时中断模型"


def test_disconnected_saved_capability_test_does_not_write_late_result(monkeypatch):
    module_path = ROOT / "api" / "v1" / "endpoints" / "ai.py"
    module_spec = importlib.util.spec_from_file_location("test_ai_endpoint_disconnect", module_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec.loader is not None
    module_spec.loader.exec_module(module)

    saved_model = SimpleNamespace(
        id=32,
        base_url="https://example.com/v1",
        model="model-32",
        provider="openai-compat",
        connectivity_status="passed",
        connectivity_checked_at="2026-08-31T10:00:00+08:00",
        reasoning_status="supported",
        reasoning_profile="chat_template",
        reasoning_checked_at="2026-08-31T10:00:00+08:00",
        usage_status="supported",
        usage_checked_at="2026-08-31T10:00:00+08:00",
    )
    current_user = SimpleNamespace(id=7, real_name="模型管理员", is_superuser=False)

    async def fake_get_model(_db, model_id):
        assert model_id == saved_model.id
        return saved_model

    async def fake_probe(*_args, cancel_check=None, **_kwargs):
        assert cancel_check is not None
        assert await cancel_check() is True
        raise module.CapabilityTestCancelled

    class _Guard:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

    class _Request:
        async def is_disconnected(self):
            return True

    class _Db:
        def add(self, _item):
            raise AssertionError("终止检测不应写入检测日志")

        async def commit(self):
            pass

    monkeypatch.setattr(module, "get_model", fake_get_model)
    monkeypatch.setattr(module, "_can_manage_model", lambda _user, model: model.id == saved_model.id)
    monkeypatch.setattr(module, "resolve_model_api_key", lambda _model: "saved-secret-key")
    monkeypatch.setattr(module, "_probe_model_capabilities", fake_probe)
    monkeypatch.setattr(module, "_ai_model_concurrency_guard", lambda *_args: _Guard())

    result = asyncio.run(module.api_test_model_capabilities(saved_model.id, _Db(), current_user, _Request()))

    assert result["code"] == 400
    assert saved_model.connectivity_status == "unknown"
    assert saved_model.connectivity_checked_at is None
    assert saved_model.reasoning_status == "unknown"
    assert saved_model.reasoning_checked_at is None
    assert saved_model.usage_status == "unknown"
    assert saved_model.usage_checked_at is None


def test_failed_capability_test_skips_audit_when_browser_stopped_waiting(monkeypatch):
    """浏览器已经不等结果时，检测失败不再补记日志——中断由前端上报，否则一次检测两条记录。"""
    module_path = ROOT / "api" / "v1" / "endpoints" / "ai.py"
    module_spec = importlib.util.spec_from_file_location("test_ai_endpoint_late_failure", module_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec.loader is not None
    module_spec.loader.exec_module(module)

    saved_model = SimpleNamespace(
        id=33,
        name="断连失败模型",
        base_url="https://example.com/v1",
        model="model-33",
        provider="openai-compat",
        connectivity_status="passed",
        connectivity_checked_at="2026-08-31T10:00:00+08:00",
        reasoning_status="supported",
        reasoning_profile="chat_template",
        reasoning_checked_at="2026-08-31T10:00:00+08:00",
        usage_status="supported",
        usage_checked_at="2026-08-31T10:00:00+08:00",
    )
    current_user = SimpleNamespace(id=7, real_name="模型管理员", is_superuser=False)

    async def fake_get_model(_db, model_id):
        assert model_id == saved_model.id
        return saved_model

    async def fake_probe(*_args, cancel_check=None, **_kwargs):
        raise RuntimeError("connection reset by peer")

    class _Guard:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

    class _Request:
        async def is_disconnected(self):
            return True

    class _Db:
        def add(self, _item):
            raise AssertionError("浏览器已断开时不应写入检测日志")

        async def commit(self):
            pass

    async def fake_log_operation(**_kwargs):
        raise AssertionError("浏览器已断开时不应补记失败日志")

    monkeypatch.setattr(module, "get_model", fake_get_model)
    monkeypatch.setattr(module, "_can_manage_model", lambda _user, model: model.id == saved_model.id)
    monkeypatch.setattr(module, "resolve_model_api_key", lambda _model: "saved-secret-key")
    monkeypatch.setattr(module, "_probe_model_capabilities", fake_probe)
    monkeypatch.setattr(module, "_ai_model_concurrency_guard", lambda *_args: _Guard())
    monkeypatch.setattr(module, "log_operation", fake_log_operation)

    result = asyncio.run(module.api_test_model_capabilities(saved_model.id, _Db(), current_user, _Request()))

    assert result["code"] == 400
    assert saved_model.connectivity_status == "unknown"
    assert saved_model.reasoning_status == "unknown"
    assert saved_model.usage_status == "unknown"


def test_capability_probe_returns_after_chat_completion_without_done(monkeypatch):
    """上游已给出 finish_reason 但未关闭连接时，探针仍应正常结束。"""
    import httpx

    from services import ai_capability_service

    observed = {}

    class _Lines:
        def __init__(self):
            self._lines = [
                "data: " + json.dumps({
                    "choices": [{
                        "delta": {"content": "鸡 4 只，兔 4 只"},
                        "finish_reason": "stop",
                    }],
                }),
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._lines:
                return self._lines.pop(0)
            raise httpx.ReadTimeout("上游在完成后未关闭流")

    class _Response:
        status_code = 200
        encoding = "utf-8"
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")

        def aiter_lines(self):
            return _Lines()

        def raise_for_status(self):
            pass

        async def aclose(self):
            pass

    class _Client:
        def __init__(self, timeout):
            observed["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def build_request(self, _method, _url, *, headers, json):
            observed["payload"] = json
            return object()

        async def send(self, _request, stream):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    result = asyncio.run(
        ai_capability_service._probe_model_capabilities(
            "https://example.com/v1", "test-key", "test-model", "openai-compat",
        )
    )

    assert result["connected"] is True
    assert result["preview"] == ""
    assert "max_tokens" not in observed["payload"]
    assert "max_output_tokens" not in observed["payload"]


def test_capability_probe_allows_slow_reasoning_without_extending_prompt_too_far():
    from services import ai_capability_service

    assert ai_capability_service.CAPABILITY_PROBE_TOTAL_TIMEOUT_SECONDS == 300.0
    assert ai_capability_service.CAPABILITY_PROBE_READ_TIMEOUT_SECONDS == 300.0
    assert "2～4 步" in ai_capability_service.CAPABILITY_PROBE_PROMPT
    assert "最终答案" in ai_capability_service.CAPABILITY_PROBE_PROMPT


def test_capability_timeout_keeps_probe_diagnostics():
    from services.ai_capability_service import CapabilityProbeTimeout, _capability_error_detail

    detail = _capability_error_detail(
        CapabilityProbeTimeout("诊断：等待 300 秒、共收到 0 行，始终没收到任何数据")
    )

    assert "始终没收到任何数据" in detail


def test_capability_probe_keeps_reading_after_reasoning_until_body_and_usage(monkeypatch):
    """收到思考后不能立即断流，应继续读取正文和可能随后返回的用量。"""
    import httpx

    from services import ai_capability_service

    observed = {"lines": [], "closed": False}

    class _Lines:
        def __init__(self):
            self._lines = [
                "data: " + json.dumps({
                    "choices": [{"delta": {"reasoning_content": "先列方程"}}],
                }),
                "data: " + json.dumps({
                    "choices": [{"delta": {"content": "鸡 4 只，兔 4 只"}}],
                }),
                "data: " + json.dumps({
                    "choices": [],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }),
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._lines:
                line = self._lines.pop(0)
                observed["lines"].append(line)
                return line
            raise StopAsyncIteration

    class _Response:
        status_code = 200
        encoding = "utf-8"
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")

        def aiter_lines(self):
            return _Lines()

        def raise_for_status(self):
            pass

        async def aclose(self):
            observed["closed"] = True

    class _Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def build_request(self, _method, _url, *, headers, json):
            return object()

        async def send(self, _request, stream):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    result = asyncio.run(
        ai_capability_service._probe_model_capabilities(
            "https://example.com/v1", "test-key", "test-model", "openai-compat",
        )
    )

    assert len(observed["lines"]) == 3
    assert observed["closed"] is True
    assert result["supported"] is True
    assert result["has_usage"] is True
    assert result["usage_status"] == "supported"


def test_capability_probe_supports_responses_reasoning_body_and_usage_events(monkeypatch):
    """Responses 流同样要读到正文/收尾用量，不能因思考事件提前结束。"""
    import httpx

    from services import ai_capability_service

    observed = {"lines": [], "closed": False}

    class _Lines:
        def __init__(self):
            self._lines = [
                "data: " + json.dumps({
                    "type": "response.reasoning_summary_text.delta",
                    "delta": "先列方程",
                }),
                "data: " + json.dumps({
                    "type": "response.output_text.delta",
                    "delta": "鸡 4 只，兔 4 只",
                }),
                "data: " + json.dumps({
                    "type": "response.completed",
                    "response": {
                        "status": "completed",
                        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                    },
                }),
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._lines:
                line = self._lines.pop(0)
                observed["lines"].append(line)
                return line
            raise StopAsyncIteration

    class _Response:
        status_code = 200
        encoding = "utf-8"
        request = httpx.Request("POST", "https://example.com/v1/responses")

        def aiter_lines(self):
            return _Lines()

        def raise_for_status(self):
            pass

        async def aclose(self):
            observed["closed"] = True

    class _Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def build_request(self, _method, _url, *, headers, json):
            return object()

        async def send(self, _request, stream):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    result = asyncio.run(
        ai_capability_service._probe_model_capabilities(
            "https://example.com/v1", "test-key", "test-model", "responses",
        )
    )

    assert len(observed["lines"]) == 3
    assert observed["closed"] is True
    assert result["supported"] is True
    assert result["has_usage"] is True
    assert result["usage_status"] == "supported"


def test_capability_probe_does_not_start_output_window_on_reasoning_only(monkeypatch):
    """思考事件只记录能力，不应在正文出现前启动提前结束窗口。"""
    import httpx

    from services import ai_capability_service

    monkeypatch.setattr(ai_capability_service, "CAPABILITY_PROBE_OUTPUT_OBSERVATION_SECONDS", 0.0)
    observed = {"lines": [], "closed": False}

    class _Lines:
        def __init__(self):
            self._lines = [
                "data: " + json.dumps({
                    "choices": [{"delta": {"reasoning_content": "先思考"}}],
                }),
                "data: " + json.dumps({
                    "choices": [{"delta": {"content": "答案"}}],
                }),
                "data: " + json.dumps({
                    "choices": [],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
                }),
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._lines:
                line = self._lines.pop(0)
                observed["lines"].append(line)
                return line
            raise AssertionError("正文出现后观察窗口结束，不应继续读取上游流")

    class _Response:
        status_code = 200
        encoding = "utf-8"
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")

        def aiter_lines(self):
            return _Lines()

        def raise_for_status(self):
            pass

        async def aclose(self):
            observed["closed"] = True

    class _Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def build_request(self, _method, _url, *, headers, json):
            return object()

        async def send(self, _request, stream):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    result = asyncio.run(
        ai_capability_service._probe_model_capabilities(
            "https://example.com/v1", "test-key", "test-model", "openai-compat",
        )
    )

    assert len(observed["lines"]) == 2
    assert observed["closed"] is True
    assert result["supported"] is True
    assert result["early_terminated"] is True
    assert result["usage_status"] == "unknown"


def test_capability_probe_does_not_extend_output_window_for_each_delta(monkeypatch):
    """连续正文分片不能不断重置 5 秒窗口，避免模型持续输出导致成本失控。"""
    import httpx

    from services import ai_capability_service

    clock_values = iter([0.0, 0.0, 0.0, 0.0, 1.0, 5.1])
    def fake_time():
        try:
            return next(clock_values)
        except StopIteration:
            return 5.1

    monkeypatch.setattr(
        ai_capability_service.asyncio,
        "get_running_loop",
        lambda: SimpleNamespace(time=fake_time),
    )
    observed = {"closed": False, "read_after_window": False}

    class _Lines:
        def __init__(self):
            self._lines = [
                "data: " + json.dumps({"choices": [{"delta": {"content": "鸡 4 只"}}]}),
                "data: " + json.dumps({"choices": [{"delta": {"content": "，兔 4 只"}}]}),
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._lines:
                return self._lines.pop(0)
            observed["read_after_window"] = True
            raise AssertionError("正文持续输出不能延长提前结束窗口")

    class _Response:
        status_code = 200
        encoding = "utf-8"
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")

        def aiter_lines(self):
            return _Lines()

        def raise_for_status(self):
            pass

        async def aclose(self):
            observed["closed"] = True

    class _Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def build_request(self, _method, _url, *, headers, json):
            return object()

        async def send(self, _request, stream):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    result = asyncio.run(
        ai_capability_service._probe_model_capabilities(
            "https://example.com/v1", "test-key", "test-model", "openai-compat",
        )
    )

    assert observed["closed"] is True
    assert observed["read_after_window"] is False
    assert result["early_terminated"] is True
    assert result["usage_status"] == "unknown"


def test_capability_probe_does_not_start_output_window_inside_think_markup(monkeypatch):
    """思考标签内的内容不算真实正文，必须等闭合标签后的答案出现。"""
    import httpx

    from services import ai_capability_service

    monkeypatch.setattr(ai_capability_service, "CAPABILITY_PROBE_OUTPUT_OBSERVATION_SECONDS", 0.0)
    observed = {"lines": [], "closed": False}

    class _Lines:
        def __init__(self):
            self._lines = [
                "data: " + json.dumps({"choices": [{"delta": {"content": "<think>先思考</think>"}}]}),
                "data: " + json.dumps({"choices": [{"delta": {"content": "答案"}}]}),
                "data: " + json.dumps({
                    "choices": [],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
                }),
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._lines:
                line = self._lines.pop(0)
                observed["lines"].append(line)
                return line
            raise AssertionError("思考标签内的内容不应触发提前结束")

    class _Response:
        status_code = 200
        encoding = "utf-8"
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")

        def aiter_lines(self):
            return _Lines()

        def raise_for_status(self):
            pass

        async def aclose(self):
            observed["closed"] = True

    class _Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def build_request(self, _method, _url, *, headers, json):
            return object()

        async def send(self, _request, stream):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    result = asyncio.run(
        ai_capability_service._probe_model_capabilities(
            "https://example.com/v1", "test-key", "test-model", "openai-compat",
        )
    )

    assert len(observed["lines"]) == 2
    assert observed["closed"] is True
    assert result["supported"] is True
    assert result["early_terminated"] is True
    assert result["usage_status"] == "unknown"


def test_capability_probe_closes_upstream_after_output_observation_window(monkeypatch):
    """正文开始后观察窗口结束就关闭上游，未拿到用量只能记为未知。"""
    import httpx

    from services import ai_capability_service

    monkeypatch.setattr(ai_capability_service, "CAPABILITY_PROBE_OUTPUT_OBSERVATION_SECONDS", 0.0)
    observed = {"closed": False, "read_after_output": False}

    class _Lines:
        def __init__(self):
            self._first = True

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._first:
                self._first = False
                return "data: " + json.dumps({
                    "choices": [{"delta": {"content": "鸡 4 只，兔 4 只"}}],
                })
            observed["read_after_output"] = True
            raise AssertionError("观察窗口结束后不应继续读取上游流")

    class _Response:
        status_code = 200
        encoding = "utf-8"
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")

        def aiter_lines(self):
            return _Lines()

        def raise_for_status(self):
            pass

        async def aclose(self):
            observed["closed"] = True

    class _Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def build_request(self, _method, _url, *, headers, json):
            return object()

        async def send(self, _request, stream):
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    result = asyncio.run(
        ai_capability_service._probe_model_capabilities(
            "https://example.com/v1", "test-key", "test-model", "openai-compat",
        )
    )

    assert observed["closed"] is True
    assert observed["read_after_output"] is False
    assert result["early_terminated"] is True
    assert result["has_usage"] is False
    assert result["usage_status"] == "unknown"


def test_capability_result_marks_unobserved_usage_as_unknown():
    from services.ai_capability_service import _capability_result_payload

    result = _capability_result_payload({
        "supported": False,
        "profile": "none",
        "preview": "",
        "has_usage": False,
        "usage_status": "unknown",
        "usage": {},
    })

    assert result["usage_status"] == "unknown"


def test_capability_probe_can_reuse_workbench_provider_without_output_limit():
    """能力检测应走与工作台相同的模型适配器，而不是另造一套请求。"""
    from services import ai_capability_service

    observed = {}

    class _Provider:
        async def _chat_with_meta_stream(self, system_prompt, user_text, **kwargs):
            observed.update(system_prompt=system_prompt, user_text=user_text, kwargs=kwargs)
            return {
                "content": "鸡 4 只，兔 4 只",
                "usage": {},
                "finish_reason": "stop",
                "early_terminated": True,
            }

    result = asyncio.run(
        ai_capability_service._probe_model_capabilities(
            "https://example.com/v1", "test-key", "test-model", "openai-compat",
            provider=_Provider(),
        )
    )

    assert observed["system_prompt"] == "You are a helpful assistant."
    assert observed["user_text"] == ai_capability_service.CAPABILITY_PROBE_PROMPT
    assert observed["kwargs"]["max_tokens"] is None
    assert observed["kwargs"]["json_mode"] is False
    assert observed["kwargs"]["stop_after_output_seconds"] == 5.0
    assert result["connected"] is True
    assert result["early_terminated"] is True


def test_workbench_provider_closes_upstream_after_capability_output_window(monkeypatch):
    """统一适配器在检测提前结束时必须退出流上下文，避免上游继续生成。"""
    import httpx

    from llm.providers.openai_compat import OpenAICompatProvider

    observed = {"read_after_output": False, "closed": False}

    class _Lines:
        def __init__(self):
            self._lines = [
                "data: " + json.dumps({"choices": [{"delta": {"content": "答案"}}]}),
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._lines:
                return self._lines.pop(0)
            observed["read_after_output"] = True
            raise AssertionError("提前结束后不应继续读取上游流")

    class _Response:
        status_code = 200
        is_success = True
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            observed["closed"] = True
            return False

        def raise_for_status(self):
            pass

        def aiter_lines(self):
            return _Lines()

        async def aread(self):
            return b""

    class _Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def stream(self, *_args, **_kwargs):
            observed["payload"] = _kwargs["json"]
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    result = asyncio.run(
        OpenAICompatProvider("test-key", "https://example.com/v1", "test-model")._chat_with_meta_stream(
            "You are a helpful assistant.",
            "请回答：1+1 等于多少？",
            timeout=10,
            max_tokens=None,
            stop_after_output_seconds=0,
        )
    )

    assert result["content"] == "答案"
    assert result["early_terminated"] is True
    assert observed["read_after_output"] is False
    assert observed["closed"] is True
    assert "max_tokens" not in observed["payload"]
    assert "max_output_tokens" not in observed["payload"]
