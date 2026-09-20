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


def test_model_management_uses_configured_balance_query_instead_of_deepseek_only_logic():
    source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")

    balance_endpoint = source[source.index('async def api_check_model_balance'):source.index('def _model_list_urls')]
    assert "fetch_billing_balance" in balance_endpoint
    assert '"deepseek.com"' not in balance_endpoint


def test_balance_query_is_available_after_enabled_configuration_passes_its_test():
    source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")
    payload = source[source.index("def _model_read_payload"):source.index("def _normalize_balance_query_update")]
    endpoint = source[source.index("async def api_check_model_balance"):source.index("def _model_list_urls")]

    assert '"can_query_balance": bool(' in payload
    assert '            owner\n            and' in payload
    assert 'getattr(model, "balance_query_enabled", False)' in payload
    assert "if not _can_view_model(current_user, model):" in endpoint
    assert "if not _is_model_owner(current_user, model):" in endpoint
    assert "仅模型创建人可以查询余额" in endpoint
    assert '"balance_query_status": getattr(model, "balance_query_status", "unknown")' in payload


def test_balance_button_rejects_non_creator_even_when_configuration_is_ready():
    page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")

    assert "if (!row?.can_query_balance)" in page
    assert "仅模型创建人可以查询余额" in page


def test_balance_query_config_supports_presets_custom_headers_and_field_path():
    deepseek = ai_billing_service.normalize_balance_query_config({"preset": "deepseek"})
    assert deepseek["preset"] == "deepseek"
    assert deepseek["url"] == "https://api.deepseek.com/user/balance"
    assert deepseek["method"] == "GET"
    assert deepseek["balance_path"] == "$.balance_infos[0].total_balance"

    custom = ai_billing_service.normalize_balance_query_config({
        "preset": "custom",
        "url": "https://gateway.example.com/account",
        "method": "POST",
        "headers": [{"key": "X-Account", "value": "private-token"}],
        "balance_path": "$.payload.credit.remaining",
    })
    assert custom["headers"] == [{"key": "X-Account", "value": "private-token"}]
    assert ai_billing_service.extract_balance_amount(
        {"payload": {"credit": {"remaining": "12.50"}}},
        custom["balance_path"],
    ) == 12.5


def test_model_list_payload_never_contains_raw_balance_configuration():
    source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")
    payload = source[source.index("def _model_read_payload"):source.index("def _mask_key")]

    assert '"balance_query_config":' not in payload
    assert '"balance_query_configured"' in payload
    assert '"headers"' not in payload


def test_balance_query_endpoint_audits_both_success_and_failure_without_sensitive_config():
    source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")
    endpoint = source[source.index('async def api_check_model_balance'):source.index('def _model_list_urls')]

    assert endpoint.count("await log_operation(") >= 2
    assert "查询模型余额失败" in endpoint
    assert "balance_query_config" not in endpoint[endpoint.index("except Exception as exc"):]


def test_model_page_uses_balance_presets_and_protected_config_detail_endpoint():
    page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")
    api = (ROOT.parent / "frontend" / "src" / "api" / "ai.js").read_text(encoding="utf-8")

    for text in ("deepseek", "cc_switch", "balance_path", "headers", "getAiModelBalanceQueryConfig"):
        assert text in page
    assert "getAiModelBalanceQueryConfig" in api


def test_balance_test_returns_json_preview_and_manual_field_candidates():
    source = (ROOT / "services" / "ai_billing_service.py").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")

    assert "response_preview" in source
    assert "balance_candidates" in source
    assert "data=result" in endpoint
    assert "test_billing_config" in endpoint
    assert "未识别余额字段" in source


def test_balance_operations_are_creator_only_and_recent_query_status_is_not_a_gate():
    source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")
    payload = source[source.index("def _model_read_payload"):source.index("def _normalize_balance_query_update")]
    config_endpoint = source[source.index("async def api_get_model_balance_query_config"):source.index("async def api_test_model_billing")]
    test_endpoint = source[source.index("async def api_test_model_billing"):source.index("async def api_check_model_balance")]
    check_endpoint = source[source.index("async def api_check_model_balance"):source.index("def _model_list_urls")]

    assert 'getattr(model, "balance_query_status", "unknown") == "passed"' not in payload
    assert "if not _is_model_owner(current_user, model):" in config_endpoint
    assert "if not _is_model_owner(current_user, model):" in test_endpoint
    assert 'getattr(model, "balance_query_status", "unknown") != "passed"' not in check_endpoint


def test_balance_dialog_uses_existing_credentials_and_scrollable_response():
    page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")
    api = (ROOT.parent / "frontend" / "src" / "api" / "ai.js").read_text(encoding="utf-8")

    billing_dialog = page[page.index("<el-dialog v-model=\"billingDialogVisible\""):page.index("</el-dialog>", page.index("<el-dialog v-model=\"billingDialogVisible\""))]
    assert 'v-model="billingForm.api_key"' not in billing_dialog
    assert 'label="API Key"' not in billing_dialog
    assert "response_preview" in page
    assert "balance_candidates" in page
    assert "overflow-y: auto" in page
    assert "testAiModelBillingDraft" in api


def test_balance_probe_returns_response_preview_and_detected_field(monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"balance_infos": [{"currency": "CNY", "total_balance": "10.50"}]}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        async def get(self, _url, headers):
            assert headers["X-Test"] == "credential"
            return _Response()

    monkeypatch.setattr(ai_billing_service.httpx, "AsyncClient", lambda timeout: _Client())
    result = asyncio.run(ai_billing_service.test_billing_config(
        SimpleNamespace(id=1, name="demo", provider="openai-compat", base_url="https://example.com", model="demo", api_key_encrypted=None),
        {
            "type": "balance",
            "preset": "custom",
            "url": "https://example.com/balance",
            "method": "GET",
            "headers": [{"key": "X-Test", "value": "credential"}],
            "balance_path": "",
        },
    ))

    assert result["supported"] is True
    assert '"total_balance": "10.50"' in result["response_preview"]
    assert result["balance_candidates"] == [{"path": "$.balance_infos[0].total_balance", "value": 10.5}]
    assert ai_billing_service.extract_balance_amount({"balance_infos": [{"total_balance": 0}]}) == 0
