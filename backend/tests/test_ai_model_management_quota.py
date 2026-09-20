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


def test_usage_data_scope_is_server_enforced_by_role():
    from api.v1.endpoints import ai as ai_endpoint

    superadmin = SimpleNamespace(id=1, is_superuser=True)
    manager = SimpleNamespace(id=2, is_superuser=False)

    assert ai_endpoint._resolve_usage_user_id(superadmin, "all") is None
    assert ai_endpoint._resolve_usage_user_id(superadmin, "self") == 1
    assert ai_endpoint._resolve_usage_user_id(manager, "all") == 2


def test_usage_api_injects_current_user_into_my_model_scope(monkeypatch):
    from api.v1.endpoints import ai as ai_endpoint

    captured = {}

    async def fake_get_usage_summary(_db, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(ai_endpoint, "get_usage_summary", fake_get_usage_summary)
    superadmin = SimpleNamespace(id=9, real_name="超管", is_superuser=True, is_manager=True)

    asyncio.run(ai_endpoint.api_usage_logs(
        page=1,
        page_size=20,
        scope="all",
        user_name=None,
        phone=None,
        keyword=None,
        start_time=None,
        end_time=None,
        model=None,
        model_scope="personal",
        model_owner_scope="self",
        action=None,
        result=None,
        department=None,
        caller_type=None,
        include_stats=False,
        db=object(),
        current_user=superadmin,
    ))

    assert captured["user_id"] is None
    assert captured["filters"].model_scope == "personal"
    assert captured["filters"].model_owner_id == 9


def test_personal_model_quota_list_includes_creator_name(monkeypatch):
    from api.v1.endpoints import ai as ai_endpoint

    personal_model = SimpleNamespace(id=11, name="个人模型", scope="personal", owner_user_id=23)

    async def list_personal_models(_db):
        return [personal_model]

    class ScalarResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class RowsResult:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class Session:
        def __init__(self):
            self.results = [RowsResult([(23, "模型创建人", None)]), ScalarResult(), RowsResult([])]

        async def execute(self, _statement):
            return self.results.pop(0)

    monkeypatch.setattr(ai_endpoint, "list_models", list_personal_models)
    response = asyncio.run(ai_endpoint.api_list_personal_model_quotas(
        Session(), SimpleNamespace(id=1, is_superuser=True, is_manager=True),
    ))

    assert response["data"][0]["owner_name"] == "模型创建人"


def test_quota_rejection_is_recorded_without_quota_consumption(monkeypatch):
    model = _eligible_model(1, "模型一")
    logs = []
    ai_service = _patch_ai_service_candidates(monkeypatch, [model], {1: SimpleNamespace()})

    async def reject_quota(_user, _model):
        raise ai_service.UnifiedException(code=429, message="今日 AI 配额已用完")

    async def capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(ai_service, "_ensure_ai_quota_available_immediate", reject_quota)
    monkeypatch.setattr(ai_service, "_log_ai_usage_immediate", capture_log)

    # 自动路由下所有候选额度都用尽时，向用户展示确认过的引导文案（而非原始的逐模型额度错误），
    # 并把该引导文案作为失败原因记录下来，且不扣除任何额度。
    guidance = "平台模型「模型一」今日 AI 配额已用完。当前没有可用的其他模型，请前往「AI模型配置」完成模型配置和额度设置后再试。"
    with pytest.raises(ai_service.UnifiedException, match="当前没有可用的其他模型"):
        asyncio.run(ai_service._call_ai_for_feature(
            None,
            SimpleNamespace(id=7, real_name="测试用户", is_superuser=False),
            feature="test_workbench_requirement_completion",
            system_prompt="系统提示",
            user_content="用户内容",
            raw_mode=True,
        ))

    assert len(logs) == 1
    assert logs[0]["status"] == "failed"
    assert logs[0]["quota_consumed"] is False
    assert logs[0]["failure_reason"] == guidance


def test_unrecognized_model_json_is_recorded_as_failed_and_consumed(monkeypatch):
    """模型已返回 JSON 但不属于业务结构时，不能先记成功再由上层报错。"""
    model = _eligible_model(1, "模型一")
    logs = []

    class Provider:
        model = "provider-1"

        async def _chat_with_meta(self, *_args, **_kwargs):
            return {"content": '{"unrelated": true}', "usage": {"total_tokens": 5}}

    ai_service = _patch_ai_service_candidates(monkeypatch, [model], {1: Provider()})

    async def capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(ai_service, "_log_ai_usage_immediate", capture_log)

    with pytest.raises(ai_service.UnifiedException, match="AI 返回结构不符合预期"):
        asyncio.run(ai_service.call_ai_for_feature(
            None,
            SimpleNamespace(id=7, real_name="测试用户", is_superuser=False),
            feature="test_workbench_requirement_merge",
            system_prompt="系统提示",
            user_content="用户内容",
            required_keys=["progress", "must_confirm"],
            required_any_keys=["progress", "must_confirm"],
            allow_missing_required_keys=True,
            selected_model_id=1,
        ))

    assert len(logs) == 1
    assert logs[0]["status"] == "failed"
    assert logs[0]["quota_consumed"] is True
    assert logs[0]["failure_reason"] == "模型已返回内容，但结果解析或校验失败"


def test_insufficient_quota_error_is_not_misclassified_as_rate_limit():
    from services.ai_service import _summarize_model_attempt_error

    assert _summarize_model_attempt_error("LLM API HTTP error: 429 insufficient_quota") == "模型服务余额或额度不足"


def test_platform_model_quota_uses_configured_platform_rule_and_superusers_remain_unlimited():
    quota_service = (ROOT / "services" / "ai_quota_service.py").read_text(encoding="utf-8")
    quota_endpoint = (ROOT / "api" / "v1" / "endpoints" / "ai.py").read_text(encoding="utf-8")
    models = (ROOT / "models" / "ai_models.py").read_text(encoding="utf-8")

    assert "AiPlatformQuotaSetting" in models
    assert "get_platform_quota_setting" in quota_service
    assert "platform_quota_setting" in quota_endpoint
    # 成员额度全平台统一：不再有按成员覆盖 / 移除覆盖接口。
    assert "api_remove_user_quota_override" not in quota_endpoint
    assert "api_set_platform_quota_setting" in quota_endpoint
    assert "DEFAULT_PLATFORM_DAILY_LIMIT" not in quota_service


def test_platform_quota_applies_without_user_override(monkeypatch):
    class EmptyQuotaResult:
        def scalar_one_or_none(self):
            return None

    class EmptyQuotaDb:
        async def execute(self, _statement):
            return EmptyQuotaResult()

    async def platform_quota(_db):
        return SimpleNamespace(daily_limit=24)

    monkeypatch.setattr(ai_quota_service, "get_platform_quota_setting", platform_quota)

    # 额度模型改为“每人统一 N 次/天”，成员覆盖表 AiUserQuota 已废弃。
    assert not hasattr(ai_models, "AiUserQuota")
    assert asyncio.run(ai_quota_service.get_user_quota(EmptyQuotaDb(), 1001)) == 24


def test_superuser_personal_model_uses_personal_daily_quota(monkeypatch):
    class ScalarResult:
        def scalar_one(self):
            return 2

    class QuotaDb:
        async def execute(self, _statement):
            return ScalarResult()

    async def personal_quota(_db, _user_id, _model_id):
        return 2

    monkeypatch.setattr(ai_quota_service, "get_user_model_quota", personal_quota)

    result = asyncio.run(ai_quota_service.check_model_ai_quota(
        QuotaDb(),
        SimpleNamespace(id=3, is_superuser=True),
        SimpleNamespace(id=8, scope="personal"),
    ))

    assert result == (False, 2, 2, "我的模型今日额度已用完（2/2）", "personal")


def test_superuser_platform_model_remains_unlimited():
    class UnexpectedDb:
        async def execute(self, _statement):
            raise AssertionError("平台模型不限时不应查询个人额度")

    result = asyncio.run(ai_quota_service.check_model_ai_quota(
        UnexpectedDb(),
        SimpleNamespace(id=3, is_superuser=True),
        SimpleNamespace(id=6, scope="platform"),
    ))

    assert result == (True, 0, -1, "", "superuser")
