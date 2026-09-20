import sys
import asyncio
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_message_platform_table_names_and_columns():
    from models.models import MessageBinding, MessageChannel, MessageTemplate, SchedulePolicyBinding

    assert MessageChannel.__tablename__ == "message_channels"
    assert MessageTemplate.__tablename__ == "message_templates"
    assert MessageBinding.__tablename__ == "message_bindings"
    assert SchedulePolicyBinding.__tablename__ == "schedule_policy_bindings"

    channel_columns = {column.name for column in MessageChannel.__table__.columns}
    assert {"name", "channel_type", "webhook_url", "secret", "keyword", "is_active"} <= channel_columns

    template_columns = {column.name for column in MessageTemplate.__table__.columns}
    assert {"name", "module", "event_type", "content", "variables", "is_default", "is_active"} <= template_columns

    binding_columns = {column.name for column in MessageBinding.__table__.columns}
    assert {"module", "target_type", "target_id", "event_type", "template_id", "channel_ids", "config"} <= binding_columns

    schedule_binding_columns = {column.name for column in SchedulePolicyBinding.__table__.columns}
    assert {"policy_id", "module", "target_type", "target_id", "is_enabled"} <= schedule_binding_columns


def test_render_template_replaces_braced_values_without_crashing_on_missing_values():
    from services.message_service import render_template

    content = "项目：{project_name}\n结果：{status}\n缺失：{missing}"
    rendered = render_template(content, {"project_name": "Smart Test", "status": "success"})

    assert rendered == "项目：Smart Test\n结果：success\n缺失："


def test_default_templates_are_scoped_by_module_and_event():
    from services.message_service import DEFAULT_MESSAGE_TEMPLATES

    keys = {(item["module"], item["event_type"]) for item in DEFAULT_MESSAGE_TEMPLATES}
    assert ("api_test", "execution_report") in keys
    assert len(keys) == 1


def test_api_execution_report_default_template_uses_compact_report_layout():
    from services.message_service import API_EXECUTION_REPORT_TEMPLATE

    assert API_EXECUTION_REPORT_TEMPLATE.startswith("# 【{project_name}】项目API测试报告")
    assert "### 执行信息" in API_EXECUTION_REPORT_TEMPLATE
    assert "### 测试结果" in API_EXECUTION_REPORT_TEMPLATE
    assert "| 运行环境 | `{env_name}` |" in API_EXECUTION_REPORT_TEMPLATE
    assert "| 执行耗时 | **{duration}s** |" in API_EXECUTION_REPORT_TEMPLATE
    assert "| **{total_cases}** | **{passed_cases}** | **{failed_cases_styled}** | **{pass_rate_styled}** |" in API_EXECUTION_REPORT_TEMPLATE
    assert "## 结果概览" not in API_EXECUTION_REPORT_TEMPLATE
    # 卡片底部已有「查看详情」按钮，正文不再重复放报告链接
    assert "{report_url}" not in API_EXECUTION_REPORT_TEMPLATE
    # 模板统一不使用 emoji
    assert not any(char in API_EXECUTION_REPORT_TEMPLATE for char in "🧪⚙️📊🌍⏱️📋✅❌📈🔗👉")


def test_channel_keyword_is_not_duplicated_when_already_in_content():
    from services.message_service import apply_channel_keyword

    assert apply_channel_keyword("【古脉】项目API测试报告", "古脉") == "【古脉】项目API测试报告"
    assert apply_channel_keyword("报告正文", "古脉") == "古脉\n报告正文"
    assert apply_channel_keyword("报告正文", None) == "报告正文"
    assert apply_channel_keyword("报告正文", "  ") == "报告正文"


def test_report_url_uses_hash_route_and_keeps_report_id():
    from services.report_sender import build_report_url

    assert build_report_url("https://smart-test.example/", 11, 42) == (
        "https://smart-test.example/#/project/11/reports?report_id=42"
    )


def test_report_url_keeps_frontend_sub_path_prefix():
    from services.report_sender import build_report_url

    assert build_report_url("https://demo.group-ds.com/tc-smart-test-frontend/", 12, 35) == (
        "https://demo.group-ds.com/tc-smart-test-frontend/#/project/12/reports?report_id=35"
    )


def test_frontend_base_url_from_referer_keeps_sub_path():
    from api.v1.endpoints.reports import _base_url_from_referer

    assert _base_url_from_referer(
        "https://demo.group-ds.com/tc-smart-test-frontend/"
    ) == "https://demo.group-ds.com/tc-smart-test-frontend"
    assert _base_url_from_referer(
        "https://demo.group-ds.com/tc-smart-test-frontend/index.html"
    ) == "https://demo.group-ds.com/tc-smart-test-frontend"
    assert _base_url_from_referer("http://localhost:3000/") == "http://localhost:3000"
    assert _base_url_from_referer("") == ""


def test_template_reference_message_contains_project_and_execution_set():
    from api.v1.endpoints.message_config import _template_reference_message

    assert _template_reference_message("古脉", "回归执行") == (
        "消息模板已被【古脉】项目的【回归执行】执行集引用，不能删除"
    )


def test_template_reference_check_matches_execution_set_notification_config():
    from api.v1.endpoints.message_config import _config_references_template

    assert _config_references_template({"message_template_id": 12}, 12)
    assert _config_references_template({"template_id": "12"}, 12)
    assert not _config_references_template({"message_template_id": 13}, 12)
    assert not _config_references_template({}, 12)


def test_channel_reference_check_matches_execution_set_notification_config():
    from api.v1.endpoints.message_config import _channel_reference_message, _config_references_channel

    assert _config_references_channel({"channel_ids": [12]}, 12)
    assert _config_references_channel({"notification_config_ids": ["12"]}, 12)
    assert _config_references_channel({"notification_config_id": 12}, 12)
    assert not _config_references_channel({"channel_ids": [13]}, 12)
    assert not _config_references_channel({}, 12)
    assert _channel_reference_message(2, 5) == "删除失败！该渠道已被2个项目的5个执行集选择；请先手动在对应的执行集下取消选择后再删除。"


def test_execution_notification_config_normalizes_legacy_aliases():
    from services.message_service import normalize_execution_notification_config

    assert normalize_execution_notification_config({
        "notification_config_ids": ["2", 2],
        "message_template_id": "4",
        "send_mode": "scheduled",
    }) == {
        "channel_ids": [2],
        "template_id": 4,
    }


def test_execution_notification_config_rejects_invalid_ids():
    from services.message_service import normalize_execution_notification_config

    with pytest.raises(ValueError, match="消息群配置"):
        normalize_execution_notification_config({"channel_ids": ["not-an-id"]})

    with pytest.raises(ValueError, match="消息模板配置"):
        normalize_execution_notification_config({"template_id": "not-an-id"})


def test_empty_notification_config_is_allowed_only_for_manual_execution():
    from core.response import UnifiedException
    from services.message_service import validate_execution_notification_config

    assert asyncio.run(validate_execution_notification_config(
        None,
        {},
        automatic=False,
    )) == {"channel_ids": [], "template_id": None}

    with pytest.raises(UnifiedException, match="自动执行必须配置消息群和消息模板"):
        asyncio.run(validate_execution_notification_config(
            None,
            {},
            automatic=True,
        ))
