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


def test_model_rejection_before_a_valid_response_is_recorded_without_quota(monkeypatch):
    model = _eligible_model(1, "模型一")
    logs = []

    class RejectedProvider:
        model = "provider-1"

        async def _chat_with_meta(self, *_args, **_kwargs):
            raise RuntimeError("LLM API HTTP error: insufficient_quota: balance exhausted")

    ai_service = _patch_ai_service_candidates(monkeypatch, [model], {1: RejectedProvider()})

    async def capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(ai_service, "_log_ai_usage_immediate", capture_log)

    async def emit(_event):
        return None

    with pytest.raises(Exception):
        asyncio.run(ai_service._call_ai_for_feature(
            None,
            SimpleNamespace(id=7, is_superuser=False),
            feature="test_workbench_requirement_completion",
            system_prompt="系统提示",
            user_content="用户内容",
            raw_mode=True,
            stream_callback=emit,
        ))

    assert len(logs) == 1
    assert logs[0]["status"] == "failed"
    assert logs[0]["quota_consumed"] is True
    assert "模型服务余额或额度不足" in logs[0]["failure_reason"]


def test_usage_record_also_creates_a_plain_language_audit_entry(monkeypatch):
    from services import ai_service

    usage_records = []
    audit_records = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        def add(self, record):
            usage_records.append(record)

        async def commit(self):
            return None

    async def capture_audit(**kwargs):
        audit_records.append(kwargs)

    monkeypatch.setattr(ai_service, "AsyncSessionLocal", Session)
    monkeypatch.setattr(ai_service, "AiUsageLog", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(ai_service, "log_operation", capture_audit, raising=False)

    asyncio.run(ai_service._log_ai_usage_immediate(
        user_id=7,
        user_name="测试用户",
        action="tw_requirement_refinement",
        model="model-1",
        model_id=1,
        target_type="requirement",
        target_id=11,
        tokens_estimated=1,
        feature="test_workbench_requirement_completion",
        status="failed",
        failure_reason="模型服务余额或额度不足",
        quota_consumed=False,
    ))

    assert usage_records[0].status == "failed"
    assert usage_records[0].quota_consumed is False
    assert len(audit_records) == 1
    assert isinstance(audit_records[0].pop("db"), Session)
    assert audit_records[0] == {
        "user_id": 7,
        "user_name": "测试用户",
        "module": "ai_call",
        "operation": "模型调用失败",
        "target_id": 11,
        "target_name": "model-1",
        "description": "AI需求补全：模型调用失败",
    }


def test_usage_list_hides_internal_fields_and_opens_failure_detail():
    source = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiUsage.vue").read_text(encoding="utf-8")
    table = source[source.index('<el-table :data="logs"'):source.index('</el-table>', source.index('<el-table :data="logs"'))]

    assert 'label="功能"' in table
    assert 'label="调用分组"' not in table
    assert "failureDetailVisible" in source
    assert "查看详情" in table


def test_tabbed_admin_lists_follow_workbench_toolbar_layout():
    model_page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")

    assert 'class="model-tabs-row"' in model_page
    assert 'class="list-toolbar"' in model_page
    assert 'class="toolbar-form"' in model_page
    assert 'class="toolbar-buttons"' in model_page
    assert 'class="toolbar-row"' not in model_page
    assert model_page.index('class="model-tabs-row"') < model_page.index('class="list-toolbar"')
    assert model_page.index('@click="openRules"') > model_page.index('class="list-toolbar"')


def test_my_models_toolbar_has_no_scope_filter_or_explanatory_hint():
    model_page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")
    model_header = model_page[model_page.index('<div class="page-header">'):model_page.index('<div class="scroll-area"')]

    assert '平台模型可查看并设置自己的权重；个人模型仅模型创建人可配置。' not in model_header
    assert 'label="范围"' not in model_header
    assert 'v-model="currentModelFilters.scope"' not in model_header
    assert 'class="model-tabs-row"' in model_header


def test_management_empty_state_uses_workbench_empty_illustration():
    source = (ROOT.parent / "frontend" / "src" / "components" / "GlobalEmpty.vue").read_text(encoding="utf-8")

    assert '<el-empty' in source
    assert ':description="text"' in source
    assert ':image-size="imageSize"' in source
    assert 'InfoFilled' not in source


def test_model_and_quota_management_operations_are_audited():
    source = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")

    fetch_endpoint = source[source.index("async def api_fetch_models"):source.index('@router.delete("/models/{model_id}")')]
    draft_check_endpoint = source[source.index("async def api_test_model_capabilities_draft"):source.index("# ---- Quota Management ----")]
    # 成员额度改为全平台统一后，唯一可写的额度接口是平台模型额度配置，且必须审计。
    quota_endpoint = source[source.index("async def api_set_platform_quota_setting"):source.index('@router.get("/usage/logs")')]

    assert "await log_operation(" in fetch_endpoint
    assert "await log_operation(" in draft_check_endpoint
    assert quota_endpoint.count("await log_operation(") >= 1


def test_model_enabled_state_changes_have_specific_audit_operations():
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")
    update_endpoint = endpoint[endpoint.index('async def api_update_model'):endpoint.index('@router.get("/models/{model_id}")')]

    assert 'operation = "启用" if updated.enabled else "停用"' in update_endpoint
    assert 'description=f"{operation}AI模型：{updated.name}"' in update_endpoint


def test_ai_model_audit_operations_are_rendered_in_the_audit_page():
    audit_source = (ROOT.parent / "frontend" / "src" / "utils" / "auditContent.js").read_text(encoding="utf-8")

    for operation in (
        "启用", "停用", "模型能力检测",
        "测试余额接口", "查询余额", "设置平台模型额度", "设置我的模型额度",
        "拉取模型列表",
    ):
        assert f"'{operation}'" in audit_source
    # 新建未保存的模型与已保存模型统一记为「模型能力检测」，不再出现草稿态取值。
    assert "草稿" not in audit_source
    # 操作类型只描述做了什么，成功/失败不再各占一个类型。
    for retired in ("能力检测失败", "终止能力检测", "能力检测中断", "拉取模型列表失败",
                    "余额接口测试失败", "查询余额失败"):
        assert f"'{retired}'" not in audit_source


def test_ai_model_audit_content_hides_model_alias():
    audit_source = (ROOT.parent / "frontend" / "src" / "utils" / "auditContent.js").read_text(encoding="utf-8")

    assert "ai_model: '模型'" in audit_source
    assert "const operation = getOperationName(row?.operation)" in audit_source
    assert "appendAuditTarget" not in audit_source


def test_platform_quota_page_warns_when_no_routable_model_is_enabled():
    model_page = (ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiModels.vue").read_text(encoding="utf-8")

    assert "const hasAvailablePlatformModel = computed" in model_page
    assert "model.scope === 'platform' && model.enabled" in model_page
    assert "当前无可用平台模型，额度暂不生效" in model_page


def test_interrupted_call_after_a_valid_response_is_recorded_as_failed(monkeypatch):
    model = _eligible_model(1, "模型一")
    logs = []

    class InterruptedProvider:
        model = "provider-1"

        async def _chat_with_meta_stream(self, *_args, on_response_observed, **_kwargs):
            await on_response_observed()
            raise RuntimeError("LLM API error: ReadTimeout")

    ai_service = _patch_ai_service_candidates(monkeypatch, [model], {1: InterruptedProvider()})

    async def capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(ai_service, "_log_ai_usage_immediate", capture_log)

    async def emit(_event):
        return None

    with pytest.raises(Exception):
        asyncio.run(ai_service._call_ai_for_feature(
            None,
            SimpleNamespace(id=7, is_superuser=False),
            feature="test_workbench_requirement_completion",
            system_prompt="系统提示",
            user_content="用户内容",
            raw_mode=True,
            stream_callback=emit,
        ))

    assert len(logs) == 1
    assert logs[0]["status"] == "failed"
    assert logs[0]["quota_consumed"] is False


def test_ai_stream_uses_user_facing_feature_labels():
    from services.ai_service import _ai_call_stage_name

    assert _ai_call_stage_name("tw_requirement_refinement", "test_workbench_requirement_completion") == "AI需求补全"
    assert _ai_call_stage_name("tw_requirement_merge_result_comparison", "test_workbench_requirement_merge") == "AI需求合并"
    assert _ai_call_stage_name("tw_test_case_generate", "test_workbench_test_case_generate") == "AI生成测试用例"
    assert _ai_call_stage_name("unrecognized_action", "test_workbench_requirement_completion") == "AI需求补全"


def test_usage_log_normalizes_legacy_result_statuses_for_display():
    from services.ai_quota_service import normalize_usage_status

    assert normalize_usage_status("completed") == "succeeded"
    assert normalize_usage_status("success") == "succeeded"
    assert normalize_usage_status("failure") == "failed"
    assert normalize_usage_status("unknown") == "failed"


def test_usage_statistics_distinguish_actual_calls_deductions_and_results():
    source = (ROOT / "services" / "ai_quota_service.py").read_text(encoding="utf-8")

    for field in (
        "actual_calls",
        "quota_consumed_calls",
        "succeeded_calls",
        "failed_calls",
    ):
        assert f'"{field}"' in source


def test_usage_records_expose_current_quota_context():
    source = (ROOT / "services" / "ai_quota_service.py").read_text(encoding="utf-8")

    assert '"model_scope":' in source
    assert '"quota_limit":' in source
    assert '"platform_quota":' in source


def test_usage_summary_resolves_quota_limit_from_joined_model_scope():
    class Result:
        def __init__(self, *, scalar=None, rows=()):
            self.scalar = scalar
            self.rows = list(rows)

        def scalar_one(self):
            return self.scalar

        def scalar_one_or_none(self):
            return self.scalar

        def all(self):
            return self.rows

    usage_log = SimpleNamespace(
        id=1,
        user_id=7,
        action="ai_call",
        model="model-3",
        target_type=None,
        target_id=None,
        tokens_estimated=10,
        model_id=3,
        feature=None,
        status="succeeded",
        failure_reason=None,
        quota_consumed=True,
        quota_count=1,
        quota_scope="superuser",
        call_group_id=None,
        created_at=None,
    )

    class Session:
        def __init__(self):
            self.results = [
                Result(scalar=1),
                Result(rows=[(usage_log, "测试用户", "15000000000", True, "personal")]),
                Result(scalar=SimpleNamespace(daily_limit=5)),
                Result(rows=[(7, 3, 10)]),
                Result(scalar=1),
            ]

        async def execute(self, _statement):
            return self.results.pop(0)

    result = asyncio.run(ai_quota_service.get_usage_summary(Session(), include_stats=False))

    assert result["items"][0]["model_scope"] == "personal"
    assert result["items"][0]["quota_limit"] == 10


def test_current_quota_limit_uses_latest_scope_rule():
    from services.ai_quota_service import resolve_current_quota_limit

    assert resolve_current_quota_limit("platform", False, 5) == 5
    assert resolve_current_quota_limit("personal", False, 5, personal_limit=10) == 10
    assert resolve_current_quota_limit("platform", True, 5) == -1
    assert resolve_current_quota_limit("personal", True, 5, personal_limit=10) == 10
    assert resolve_current_quota_limit("superuser", True, 5, personal_limit=10, model_scope="personal") == 10
    assert resolve_current_quota_limit("personal", False, 5, personal_limit=0) == 0
