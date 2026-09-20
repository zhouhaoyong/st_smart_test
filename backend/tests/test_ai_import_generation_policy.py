import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_import.generation import (
    coverage_plan,
    estimate_generation,
    extra_case_limit,
    generation_batch_audit_description,
    generation_failure_message,
    generation_failure_type,
    generation_result_message,
    plan_generation_batches,
    resolve_operation_type,
)
from services.ai_import.summary import (
    apply_case_changes,
    assertion_for_case_type,
    build_system_generated_case,
    case_request_signature,
    detail_for_generate,
    merge_generated_cases,
)
from api.v1.endpoints.import_ai import generation_context_for_preview


def test_operation_type_prefers_analysis_then_falls_back_to_method():
    assert resolve_operation_type({"operation_type": "auth", "method": "GET"}) == "auth"
    assert resolve_operation_type({"method": "DELETE", "url": "/users/1"}) == "delete"
    assert resolve_operation_type({"method": "GET", "url": "/users"}) == "read"
    assert resolve_operation_type({"method": "POST", "url": "/users"}) == "write"
    assert resolve_operation_type({"method": "POST", "url": "/auth/login"}) == "auth"


def test_generation_timeout_has_stable_business_failure_message_and_audit_description():
    raw_reason = "timeout of 600000ms exceeded"

    assert generation_failure_type(raw_reason) == "timeout"
    assert generation_failure_message(raw_reason) == "AI模型响应超时，等待超过10分钟"
    assert generation_batch_audit_description(8, 8, 8, 0, 8, raw_reason) == (
        "用例生成：第 8/8 批处理 8 个接口失败，原因：模型响应超时"
    )
    assert resolve_operation_type({"method": "TRACE", "url": "/x"}) == "other"


def test_main_mode_never_needs_ai():
    for op in ("read", "write", "delete", "auth", "other"):
        assert extra_case_limit("main", op) == 0
    estimate = estimate_generation([{"method": "GET", "url": "/users"}] * 30, "main")
    assert estimate["ai_calls"] == 0
    assert estimate["cases"] == 30


def test_coverage_depth_scales_with_mode_and_operation_type():
    assert extra_case_limit("full", "write") > extra_case_limit("normal", "write")
    assert extra_case_limit("normal", "write") > extra_case_limit("normal", "delete")


def test_coverage_plan_excludes_main_and_matches_mode():
    plan = coverage_plan({"temp_id": "t1", "method": "POST", "url": "/users"}, "normal")
    assert plan["operation_type"] == "write"
    assert plan["case_types"] == ["reverse"]
    assert plan["max_cases"] == extra_case_limit("normal", "write")
    assert set(plan["focus"]) == {"reverse"}

    full_plan = coverage_plan({"temp_id": "t1", "method": "POST", "url": "/users"}, "full")
    assert full_plan["case_types"] == ["reverse", "abnormal"]


def test_batches_target_six_to_ten_interfaces_and_keep_last_batch_small_when_needed():
    def lengths(count):
        plans = [{"temp_id": f"t{i}", "max_cases": 7} for i in range(count)]
        return [len(batch) for batch in plan_generation_batches(plans)]

    assert lengths(1) == [1]
    assert lengths(10) == [10]
    assert lengths(11) == [6, 5]
    assert lengths(13) == [7, 6]
    assert lengths(21) == [7, 7, 7]
    assert all(size <= 10 for size in lengths(100))


def test_batch_split_does_not_depend_on_incremental_case_budget():
    plans = [{"temp_id": f"t{i}", "max_cases": 1} for i in range(30)]

    assert [len(batch) for batch in plan_generation_batches(plans)] == [10, 10, 10]


def test_generation_context_uses_interface_case_flow_for_every_preview():
    assert generation_context_for_preview({"source": "interface_case_generate"}) == {
        "feature": "api_interface_case_generate",
        "audit_module": "interface_case_generate",
        "target_type": "interface_batch",
    }
    assert generation_context_for_preview({"source": "ai_import"}) == {
        "feature": "api_interface_case_generate",
        "audit_module": "interface_case_generate",
        "target_type": "interface_batch",
    }


def test_all_new_cases_get_the_same_business_code_assertion():
    for case_type in ("main", "reverse", "abnormal"):
        assertion = assertion_for_case_type(case_type)[0]
        assert assertion["operator"] == "eq"
        assert assertion["expected"] == "200"


def test_generated_assertion_carries_no_expected_type_field():
    """断言只按值比较，不带数据类型字段：这个字段运行时不参与判定，别再加回来。"""
    cases = build_system_generated_case({
        "name": "用户详情",
        "method": "GET",
        "url": "/users/me",
        "response_meta": {"field_types": {"code": "int"}},
        "response_example": '{"code": 200}',
    })

    assert "expected_type" not in cases[0]["assertions"][0]


def test_apply_case_changes_only_touches_declared_fields():
    base = {
        "query_params": [{"key": "status", "value": "1"}, {"key": "page", "value": "1"}],
        "path_params": [],
        "headers": [],
        "body_type": "none",
        "body_content": "",
    }
    overrides, warnings = apply_case_changes(base, [
        {"target": "query", "field": "status", "action": "remove"},
        {"target": "query", "field": "page", "action": "set", "value": "-1"},
    ])

    assert [p["key"] for p in overrides["query_params"]] == ["page"]
    assert overrides["query_params"][0]["value"] == "-1"
    assert warnings == []
    # 原始主流程参数不被就地改写
    assert [p["key"] for p in base["query_params"]] == ["status", "page"]


def test_system_case_uses_interface_values_without_ai_wording():
    cases = build_system_generated_case({
        "name": "用户详情",
        "method": "GET",
        "url": "/users/{id}",
        "path_params": [{"key": "id", "value": "1"}],
        "query_params": [],
        "headers": [],
    })
    case = cases[0]

    assert case["case_type"] == "main"
    assert case["param_overrides"]["path_params"] == [{"key": "id", "value": "1"}]
    assert "AI" not in case["description"]
    assert "AI" not in " ".join(case["warnings"])


def test_system_case_marks_required_parameters_without_examples_for_follow_up():
    case = build_system_generated_case({
        "name": "用户列表",
        "method": "GET",
        "url": "/users",
        "query_params": [{"key": "status", "value": "", "required": True}],
    })[0]

    assert case["todo"] == ["请补充必填参数：查询参数 status"]
    assert case["warnings"] == ["存在必填参数未提供示例值"]


def test_system_case_marks_required_body_fields_without_examples_for_follow_up():
    case = build_system_generated_case({
        "name": "创建用户",
        "method": "POST",
        "url": "/users",
        "body_type": "json",
        "body_content": '{"name":""}',
        "body_required_fields": ["name"],
    })[0]

    assert case["todo"] == ["请补充必填参数：请求体字段 name"]
    assert case["warnings"] == ["存在必填参数未提供示例值"]


def test_system_case_is_described_as_an_editable_request_draft():
    case = build_system_generated_case({
        "name": "用户详情",
        "method": "GET",
        "url": "/users/{id}",
        "path_params": [{"key": "id", "value": ""}],
    })[0]

    assert case["description"] == "根据接口定义生成的基础请求用例，参数可能需要补充"
    assert case["purpose"] == "提供接口请求模板，供用户检查、补充和执行"


def test_generation_detail_keeps_generic_parameter_metadata_for_value_inference():
    detail = detail_for_generate({
        "name": "查询记录",
        "method": "GET",
        "url": "/records",
        "project_id": 8,
        "query_params": [{
            "key": "record_key",
            "value": "",
            "type": "integer",
            "required": True,
            "description": "记录标识",
        }],
        "body_schema_types": {"enabled": "boolean"},
        "body_required_fields": ["enabled"],
    })

    assert detail["query_params"] == [{
        "key": "record_key",
        "value": "",
        "type": "integer",
        "required": True,
        "description": "记录标识",
    }]
    assert detail["body_schema_types"] == {"enabled": "boolean"}
    assert detail["body_required_fields"] == ["enabled"]
    assert "project_id" not in detail
    assert "service_key" not in detail


def test_generation_prompt_does_not_claim_the_base_case_was_verified():
    prompt = (ROOT / "docs" / "prompt" / "api_generate_testcases.md").read_text(encoding="utf-8")

    assert "基础用例" in prompt
    assert "不能视为已验证成功" in prompt
    assert "base_changes" in prompt
    assert "只读、查询类" in prompt
    assert "系统会统一添加 `code == 200` 断言" in prompt
    assert "业务码不等于 200" not in prompt
    assert "参数全部合法、正常调通" not in prompt


def test_generation_prompt_requires_read_candidates_for_empty_declared_values():
    prompt = (ROOT / "docs" / "prompt" / "api_generate_testcases.md").read_text(encoding="utf-8")

    assert "必须为只读、查询类接口中每个为空的已声明参数返回候选值" in prompt
    assert "不能因为不知道真实数据而留空" in prompt


def test_merge_composes_chinese_function_prefix_and_scenario_suffix():
    iface = {
        "temp_id": "t-name",
        "name": "List Test Cases",
        "method": "GET",
        "url": "/api/v1/testcases",
        "operation_type": "read",
        "query_params": [{"key": "interface_id", "value": "", "type": "integer", "required": True}],
    }
    plan = coverage_plan(iface, "normal")

    cases = merge_generated_cases(iface, {
        "case_name_prefix": "测试用例列表",
        "base_changes": [{"target": "query", "field": "interface_id", "action": "set", "value": 8}],
        "cases": [{
            "case_type": "reverse",
            "name_suffix": "缺少interface_id参数",
            "changes": [{"target": "query", "field": "interface_id", "action": "remove"}],
        }],
    }, plan)

    assert cases[0]["name"] == "测试用例列表_基础用例"
    assert cases[1]["name"] == "测试用例列表_缺少interface_id参数"
    assert cases[0]["param_overrides"]["query_params"] == [{"key": "interface_id", "value": 8}]


def test_merge_keeps_system_main_case_and_caps_ai_increment():
    iface = {
        "temp_id": "t1",
        "name": "用户列表",
        "method": "GET",
        "url": "/users",
        "query_params": [
            {"key": "status", "value": "1"},
            {"key": "page", "value": "1"},
            {"key": "size", "value": "10"},
        ],
    }
    plan = coverage_plan(iface, "normal")
    fields = ["status", "page", "size"]
    ai_cases = [
        {
            "name": f"逆向用例{i}",
            "case_type": "reverse",
            "changes": [{"target": "query", "field": fields[i % len(fields)], "action": "remove"}],
        }
        for i in range(plan["max_cases"] + 5)
    ]

    cases = merge_generated_cases(iface, ai_cases, plan)

    assert cases[0]["case_type"] == "main"
    assert len(cases) == 1 + plan["max_cases"]
    assert all(c["case_type"] != "main" for c in cases[1:])
    assert all(c["assertions"][0]["operator"] == "eq" for c in cases[1:])


def test_merge_falls_back_to_main_only_when_ai_returns_nothing():
    iface = {"temp_id": "t1", "name": "用户列表", "method": "GET", "url": "/users"}
    plan = coverage_plan(iface, "normal")

    assert len(merge_generated_cases(iface, None, plan)) == 1
    assert len(merge_generated_cases(iface, [], plan)) == 1
    # 主流程模式不允许任何增量，AI 返回内容也应被丢弃
    main_plan = coverage_plan(iface, "main")
    assert len(merge_generated_cases(iface, [{"case_type": "reverse", "changes": []}], main_plan)) == 1


def test_read_main_case_accepts_ai_values_for_missing_parameters():
    iface = {
        "temp_id": "t-read",
        "name": "查询详情",
        "method": "GET",
        "url": "/records",
        "operation_type": "read",
        "query_params": [{
            "key": "record_key",
            "value": "",
            "type": "integer",
            "required": True,
        }],
    }
    plan = coverage_plan(iface, "normal")

    cases = merge_generated_cases(iface, {
        "base_changes": [{
            "target": "query",
            "field": "record_key",
            "action": "set",
            "value": 12,
        }],
        "cases": [],
    }, plan)

    assert cases[0]["param_overrides"]["query_params"] == [{"key": "record_key", "value": 12}]
    assert cases[0]["warnings"] == []
    assert cases[0]["todo"] == []


def test_read_main_case_does_not_overwrite_existing_values():
    iface = {
        "name": "查询记录",
        "method": "GET",
        "url": "/records",
        "operation_type": "read",
        "query_params": [
            {"key": "record_key", "value": "", "type": "integer"},
            {"key": "state", "value": "active", "type": "string"},
        ],
    }
    plan = coverage_plan(iface, "normal")

    case = merge_generated_cases(iface, {
        "base_changes": [
            {"target": "query", "field": "record_key", "action": "set", "value": 12},
            {"target": "query", "field": "state", "action": "set", "value": "inactive"},
        ],
        "cases": [],
    }, plan)[0]

    assert case["param_overrides"]["query_params"] == [
        {"key": "record_key", "value": 12},
        {"key": "state", "value": "active"},
    ]


def test_read_main_case_applies_ai_candidates_to_all_declared_request_parts():
    iface = {
        "name": "查询记录详情",
        "method": "GET",
        "url": "/records/{record_id}",
        "operation_type": "read",
        "query_params": [{"key": "status", "value": "", "type": "string"}],
        "path_params": [{"key": "record_id", "value": "", "type": "integer", "required": True}],
        "headers": [{"key": "X-Trace-Id", "value": "", "type": "string"}],
    }
    plan = coverage_plan(iface, "full")

    case = merge_generated_cases(iface, {
        "case_name_prefix": "记录详情",
        "base_changes": [
            {"target": "query", "field": "status", "action": "set", "value": "active"},
            {"target": "path", "field": "record_id", "action": "set", "value": 12},
            {"target": "header", "field": "X-Trace-Id", "action": "set", "value": "trace-001"},
        ],
        "cases": [],
    }, plan)[0]

    assert case["param_overrides"]["query_params"] == [{"key": "status", "value": "active"}]
    assert case["param_overrides"]["path_params"] == [{"key": "record_id", "value": 12}]
    assert case["param_overrides"]["headers"] == [{"key": "X-Trace-Id", "value": "trace-001"}]
    assert case["todo"] == []


def test_write_main_case_does_not_accept_ai_values_for_missing_parameters():
    iface = {
        "temp_id": "t-write",
        "name": "创建记录",
        "method": "POST",
        "url": "/records",
        "operation_type": "write",
        "query_params": [{
            "key": "record_key",
            "value": "",
            "type": "integer",
            "required": True,
        }],
    }
    plan = coverage_plan(iface, "normal")

    cases = merge_generated_cases(iface, {
        "base_changes": [{
            "target": "query",
            "field": "record_key",
            "action": "set",
            "value": 12,
        }],
        "cases": [],
    }, plan)

    assert cases[0]["param_overrides"]["query_params"] == [{"key": "record_key", "value": ""}]
    assert cases[0]["todo"] == ["请补充必填参数：查询参数 record_key"]


def test_mutating_http_method_cannot_receive_read_base_value_even_if_operation_is_misclassified():
    iface = {
        "name": "创建记录",
        "method": "POST",
        "url": "/records",
        "operation_type": "read",
        "query_params": [{"key": "record_key", "value": "", "required": True}],
    }
    plan = coverage_plan(iface, "normal")

    case = merge_generated_cases(iface, {
        "base_changes": [{"target": "query", "field": "record_key", "action": "set", "value": 12}],
        "cases": [],
    }, plan)[0]

    assert case["param_overrides"]["query_params"] == [{"key": "record_key", "value": ""}]
    assert case["todo"] == ["请补充必填参数：查询参数 record_key"]


def test_read_main_case_can_create_missing_json_body_fields():
    iface = {
        "name": "查询开关",
        "method": "GET",
        "url": "/flags",
        "operation_type": "read",
        "body_type": "json",
        "body_content": "",
        "body_schema_types": {"enabled": "boolean"},
        "body_required_fields": ["enabled"],
    }
    plan = coverage_plan(iface, "normal")

    case = merge_generated_cases(iface, {
        "base_changes": [{"target": "body", "field": "enabled", "action": "set", "value": True}],
        "cases": [],
    }, plan)[0]

    assert json.loads(case["param_overrides"]["body_content"]) == {"enabled": True}
    assert case["todo"] == []


def test_read_main_case_applies_nested_json_body_fields_at_their_declared_path():
    iface = {
        "name": "查询记录",
        "method": "GET",
        "url": "/records/search",
        "operation_type": "read",
        "body_type": "json",
        "body_content": '{"filter": {"record_key": ""}}',
        "body_schema_types": {"filter.record_key": "integer"},
        "body_required_fields": ["filter.record_key"],
    }
    plan = coverage_plan(iface, "normal")

    case = merge_generated_cases(iface, {
        "base_changes": [{
            "target": "body",
            "field": "filter.record_key",
            "action": "set",
            "value": 12,
        }],
        "cases": [],
    }, plan)[0]

    assert json.loads(case["param_overrides"]["body_content"]) == {"filter": {"record_key": 12}}
    assert case["todo"] == []


def test_merge_deduplicates_same_request_intent_and_keeps_code_assertion():
    iface = {
        "temp_id": "t-dedup",
        "name": "查询记录",
        "method": "GET",
        "url": "/records",
        "query_params": [{
            "key": "record_key",
            "value": "1",
            "type": "integer",
        }],
    }
    plan = coverage_plan(iface, "full")
    ai_cases = [
        {
            "name": "缺少记录标识",
            "case_type": "reverse",
            "priority": "high",
            "changes": [{"target": "query", "field": "record_key", "action": "remove"}],
        },
        {
            "name": "缺少记录标识（重复）",
            "case_type": "reverse",
            "priority": "medium",
            "changes": [{"target": "query", "field": "record_key", "action": "remove"}],
        },
        {
            "name": "记录标识类型错误",
            "case_type": "reverse",
            "priority": "high",
            "changes": [{"target": "query", "field": "record_key", "action": "set", "value": "abc"}],
        },
        {
            "name": "记录标识类型错误（重复）",
            "case_type": "reverse",
            "priority": "medium",
            "changes": [{"target": "query", "field": "record_key", "action": "set", "value": "abc!@#"}],
        },
    ]

    cases = merge_generated_cases(iface, ai_cases, plan)

    assert len(cases) == 3
    assert cases[1]["priority"] == "low"
    assert cases[2]["priority"] == "medium"
    assert all(case["assertions"][0]["expected"] == "200" for case in cases)


def test_merge_deduplicates_equivalent_typed_parameter_values():
    iface = {
        "name": "查询记录",
        "method": "GET",
        "url": "/records",
        "query_params": [{"key": "record_key", "value": "2", "type": "integer"}],
    }
    plan = coverage_plan(iface, "normal")
    cases = merge_generated_cases(iface, [
        {
            "case_type": "reverse",
            "changes": [{"target": "query", "field": "record_key", "action": "set", "value": 1}],
        },
        {
            "case_type": "reverse",
            "changes": [{"target": "query", "field": "record_key", "action": "set", "value": "1"}],
        },
    ], plan)

    assert len(cases) == 2


def test_request_signature_keeps_different_execution_scripts_distinct():
    iface = {"method": "GET", "url": "/records"}
    first = build_system_generated_case(iface)[0]["param_overrides"]
    second = {**first, "pre_script": "setToken('a')"}

    assert case_request_signature(iface, first) != case_request_signature(iface, second)


def test_merge_deduplicates_semantically_equivalent_main_case():
    iface = {
        "name": "查询记录",
        "method": "GET",
        "url": "/records",
        "query_params": [{"key": "record_key", "value": "1", "type": "integer"}],
    }
    plan = coverage_plan(iface, "normal")

    cases = merge_generated_cases(iface, [{
        "case_type": "reverse",
        "changes": [{"target": "query", "field": "record_key", "action": "set", "value": 1}],
    }], plan)

    assert len(cases) == 1


def test_generation_result_message_reports_interfaces_and_cases():
    assert generation_result_message(3, 7) == "用例生成完成：成功生成 3 个接口，共 7 个用例"
    assert generation_result_message(3, 7, 1) == "用例生成完成：成功生成 3 个接口，共 7 个用例；失败 1 个接口（可单独重试）"
