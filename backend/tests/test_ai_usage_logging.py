import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_usage_log_persists_token_breakdown_without_model_content(monkeypatch):
    from services import ai_service

    usage_records = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def add(self, record):
            usage_records.append(record)

        async def commit(self):
            return None

    monkeypatch.setattr(ai_service, "AsyncSessionLocal", Session)
    monkeypatch.setattr(ai_service, "AiUsageLog", lambda **kwargs: SimpleNamespace(**kwargs))

    asyncio.run(ai_service._log_ai_usage_immediate(
        user_id=None,
        user_name=None,
        action="api_interface_case_generate",
        model="claude-opus-4-8",
        model_id=5,
        target_type="ai_import_preview",
        target_id=0,
        tokens_estimated=150,
        feature="api_interface_case_generate",
        usage_summary={
            "input_tokens": 120,
            "output_tokens": 30,
            "cache_tokens": 80,
            "total_tokens": 150,
        },
        provider_request_id="resp_test_001",
    ))

    assert len(usage_records) == 1
    assert usage_records[0].input_tokens == 120
    assert usage_records[0].output_tokens == 30
    assert usage_records[0].cache_tokens == 80
    assert usage_records[0].total_tokens == 150
    assert usage_records[0].provider_request_id == "resp_test_001"
    assert not hasattr(usage_records[0], "prompt")
    assert not hasattr(usage_records[0], "response")


def test_project_scoped_ai_usage_audit_includes_project_name(monkeypatch):
    from services import ai_service

    audit_records = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def add(self, _record):
            return None

        async def commit(self):
            return None

    async def capture_audit(**kwargs):
        audit_records.append(kwargs)

    monkeypatch.setattr(ai_service, "AsyncSessionLocal", Session)
    monkeypatch.setattr(ai_service, "AiUsageLog", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(ai_service, "log_operation", capture_audit)

    asyncio.run(ai_service._log_ai_usage_immediate(
        user_id=7,
        user_name="测试用户",
        action="api_interface_case_generate",
        model="model-1",
        model_id=1,
        target_type="interface_batch",
        target_id=8,
        tokens_estimated=1,
        feature="api_interface_case_generate",
        audit_project_name="订单",
    ))

    assert audit_records[0]["description"] == "订单项目内，接口批量生成用例：模型调用成功"


def test_usage_detail_fields_are_exposed_for_auditing():
    quota_service = (ROOT / "services" / "ai_quota_service.py").read_text(encoding="utf-8")
    usage_page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiUsage.vue").read_text(encoding="utf-8")
    usage_stats_component = (ROOT.parent / "frontend" / "src" / "components" / "AiUsageStatsBar.vue").read_text(encoding="utf-8")

    for field in ("input_tokens", "output_tokens", "cache_tokens", "total_tokens", "provider_request_id"):
        assert f'"{field}": log.{field}' in quota_service
    assert "Token 用量明细" in usage_page
    assert '<AiUsageStatsBar' in usage_page
    assert 'variant="summary"' in usage_page
    assert 'layout="grid"' in usage_page
    assert ':usage="usageDetail"' in usage_page
    assert "服务商请求标识" not in usage_page
    for label in ("输入", "输出", "缓存", "总消耗"):
        assert label in usage_stats_component
    assert "ai-usage-bar--summary-grid" in usage_stats_component
    assert "grid-template-columns: repeat(2" in usage_stats_component


def test_interface_case_generation_uses_dedicated_ai_and_audit_labels():
    from services.ai_service import _shared
    from services.audit_service import AUDIT_MODULE_GROUPS

    feature = "api_interface_case_generate"

    assert _shared._AI_FEATURE_LABELS[feature] == "接口批量生成用例"
    assert _shared._AI_CALL_STAGE_FEATURES[feature] == feature
    assert feature == "api_interface_case_generate"
    assert "interface_case_generate" in AUDIT_MODULE_GROUPS["api_test"]


def test_frontend_usage_labels_distinguish_interface_case_generation():
    labels = (ROOT.parent / "frontend" / "src" / "utils" / "aiUsageLabels.js").read_text(encoding="utf-8")

    assert "api_interface_case_generate" in labels
    assert "接口批量生成用例" in labels
