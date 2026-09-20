import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_import import persist
from services.file_import_dedup import (
    CHANGE_NAME,
    diff_existing_interface,
    find_existing_interfaces,
    merge_case_overrides,
    select_existing_interface,
)
from services.interface_structure import interface_structure_fingerprint


def _interface_definition(**overrides):
    data = {
        "temp_id": "temp-1",
        "name": "用户列表",
        "operation_id": "listUsers",
        "method": "GET",
        "url": "/users",
        "query_params": [{"name": "page", "type": "integer", "required": False}],
        "path_params": [],
        "headers": [{"name": "Authorization", "type": "string", "required": True}],
        "body_type": None,
        "body_schema_types": {},
        "response_meta": {"status_codes": ["200"]},
    }
    data.update(overrides)
    return data


def _existing_interface(**overrides):
    definition = _interface_definition()
    data = {
        "id": 40,
        "name": definition["name"],
        "source_operation_id": definition["operation_id"],
        "method": definition["method"],
        "url": definition["url"],
        "query_params": definition["query_params"],
        "path_params": definition["path_params"],
        "headers": definition["headers"],
        "body_type": definition["body_type"],
        "body_content": definition.get("body_content"),
        "body_schema_types": definition["body_schema_types"],
        "definition_fingerprint": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_interface_definition_fingerprint_ignores_order_but_detects_structure_change():
    original = _interface_definition(query_params=[
        {"name": "page", "type": "integer", "required": False},
        {"name": "size", "type": "integer", "required": False},
    ])
    reordered = _interface_definition(
        query_params=list(reversed(original["query_params"])),
        headers=list(reversed(original["headers"])),
    )
    response_only = _interface_definition(
        query_params=original["query_params"],
        response_meta={"status_codes": ["500"]},
    )
    changed = _interface_definition(query_params=[
        {"name": "page", "type": "string", "required": False},
        {"name": "size", "type": "integer", "required": False},
    ])

    assert interface_structure_fingerprint(original) == interface_structure_fingerprint(reordered)
    assert interface_structure_fingerprint(original) == interface_structure_fingerprint(response_only)
    assert interface_structure_fingerprint(original) != interface_structure_fingerprint(changed)


def test_interface_definition_fingerprint_supports_array_examples():
    interface = _interface_definition(body_content='[{"id": 1}]', response_example='[{"code": 200}]')
    assert len(interface_structure_fingerprint(interface)) == 64


def test_global_match_prefers_exact_structure_among_same_url_candidates():
    incoming = _interface_definition()
    changed = _existing_interface(
        id=51,
        query_params=[{"name": "page", "type": "string", "required": False}],
    )
    exact = _existing_interface(id=52)
    assert select_existing_interface([changed, exact], incoming) is exact


def test_definition_diff_ignores_headers_and_response_but_keeps_name_change():
    existing = _existing_interface()
    incoming = _interface_definition(
        headers=[{"name": "X-Other", "type": "string"}],
        response_meta={"status_codes": ["500"]},
    )
    assert diff_existing_interface(existing, incoming) == []
    assert CHANGE_NAME in diff_existing_interface(existing, {**incoming, "name": "用户查询"})


def test_operation_id_does_not_fall_back_to_url_or_method():
    class Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class Db:
        async def execute(self, _statement):
            return Result()

    async def scenario():
        return await find_existing_interfaces(Db(), 10, _interface_definition(operation_id="renamed"))

    import asyncio
    assert asyncio.run(scenario()) == []


def test_merge_case_overrides_preserves_user_values_and_applies_explicit_param_changes():
    existing = {
        "method": "GET",
        "url": "/users",
        "query_params": [{"key": "page", "value": "7"}],
        "body_content": '{"name":"用户输入","old":"保留"}',
        "body_schema_types": {"name": "string", "old": "string"},
        "pre_script": "custom-pre",
    }
    incoming = {
        "method": "POST",
        "url": "/users/search",
        "query_params": [
            {"key": "page", "value": "1"},
            {"key": "size", "value": "20"},
        ],
        "body_type": "json",
        "body_content": '{"name":"示例","old":"示例","new":"示例"}',
        "body_schema_types": {"name": "string", "old": "string", "new": "string"},
        "post_script": "new-post",
    }

    merged = merge_case_overrides(existing, incoming)
    assert merged["method"] == "POST"
    assert merged["url"] == "/users/search"
    assert merged["query_params"] == [{"key": "page", "value": "7"}, {"key": "size", "value": ""}]
    assert merged["body_content"] == '{\n  "name": "用户输入",\n  "old": "保留",\n  "new": ""\n}'
    assert merged["pre_script"] == "custom-pre"
    assert merged["post_script"] == "new-post"


def test_merge_case_overrides_keeps_ambiguous_rename_content_for_manual_confirmation():
    existing = {
        "query_params": [{"key": "old", "value": "user-value"}],
        "body_content": '{"old":"user-value"}',
    }
    incoming = {
        "query_params": [{"key": "new", "value": "example"}],
        "body_content": '{"new":"example"}',
    }
    merged = merge_case_overrides(existing, incoming)
    assert merged["query_params"] == existing["query_params"]
    assert merged["body_content"] == existing["body_content"]


def test_interface_case_generation_filters_main_case_and_makes_names_unique():
    cases = [
        {"name": "用户列表_基础用例", "case_type": "main", "assertions": []},
        {"name": "参数为空", "case_type": "reverse", "assertions": []},
        {"name": "参数为空", "case_type": "abnormal", "assertions": []},
    ]
    selected, skipped = persist._prepare_interface_case_append(
        cases,
        existing_case_count=2,
        existing_case_names={"参数为空", "参数为空（2）"},
    )
    assert skipped == 1
    assert [case["name"] for case in selected] == ["参数为空（3）", "参数为空（4）"]
    assert all(case["case_type"] != "main" for case in selected)


def test_interface_case_generation_deduplicates_existing_request_intent():
    iface = {
        "method": "GET", "url": "/records",
        "query_params": [{"key": "record_key", "value": "1", "type": "integer"}],
        "path_params": [], "headers": [],
    }
    existing = SimpleNamespace(param_overrides={
        "method": "GET", "url": "/records",
        "query_params": [{"key": "record_key", "value": "abc"}],
        "path_params": [], "headers": [], "body_type": None, "body_content": "",
    })
    candidates = [
        {"name": "记录标识类型错误", "case_type": "reverse", "param_overrides": {
            "method": "GET", "url": "/records",
            "query_params": [{"key": "record_key", "value": "abc!@#"}],
            "path_params": [], "headers": [], "body_type": None, "body_content": "",
        }},
        {"name": "记录标识类型错误（重复）", "case_type": "reverse", "param_overrides": {
            "method": "GET", "url": "/records",
            "query_params": [{"key": "record_key", "value": "xyz"}],
            "path_params": [], "headers": [], "body_type": None, "body_content": "",
        }},
    ]
    selected, skipped = persist._prepare_interface_case_append(
        candidates, existing_case_count=1, existing_case_names=set(), iface=iface, existing_cases=[existing],
    )
    assert skipped == 0
    assert selected == []


def test_interface_case_generation_new_case_sets_creator_modifier_and_save_time():
    save_time = datetime(2026, 8, 31, 12, 34, 56, tzinfo=timezone.utc)
    case = persist._new_test_case(
        {"name": "用户列表", "assertions": []},
        project_id=10, interface_id=20, owner="测试用户", created_by=7, save_time=save_time,
    )
    assert case.created_by == 7
    assert case.updated_by == 7
    assert case.created_at == save_time
    assert case.updated_at == save_time
    assert case.assertions[0]["expression"] == "$.code"
    assert case.assertions[0]["expected"] == "200"
