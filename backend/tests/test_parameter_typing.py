import json
import unittest
from types import SimpleNamespace

from services.parameter_typing import (
    aggregate_parameter_candidates,
    collect_param_candidates,
    classify_parameter_candidate,
    infer_param_type,
    normalize_schema_type,
    resolve_parameter_contract,
    validate_parameter_value,
    walk_body_candidates,
)
from api.v1.endpoints.import_api import _parse_openapi
from api.v1.endpoints.parameter_sets import ParameterItemSchema
from api.v1.endpoints.parameter_sets_routers._shared import _ensure_unique_keys, _key_conflicts
from core.response import UnifiedException


class ParameterTypingTests(unittest.TestCase):
    def test_normalizes_openapi_schema_types(self):
        self.assertEqual(normalize_schema_type({"type": "integer"}), "int")
        self.assertEqual(normalize_schema_type({"type": "number"}), "float")
        self.assertEqual(normalize_schema_type({"type": "array"}), "list")
        self.assertEqual(normalize_schema_type({"type": "object"}), "object")
        self.assertEqual(normalize_schema_type({"type": "string"}), "string")

    def test_infers_type_from_existing_value(self):
        self.assertEqual(infer_param_type("123"), "int")
        self.assertEqual(infer_param_type("12.5"), "float")
        self.assertEqual(infer_param_type("true"), "bool")
        self.assertEqual(infer_param_type('["a"]'), "list")
        self.assertEqual(infer_param_type('{"a":1}'), "object")
        self.assertEqual(infer_param_type("abc"), "string")

    def test_string_accepts_any_text_including_json_text(self):
        self.assertIsNone(validate_parameter_value("string", '["a"]'))
        self.assertIsNone(validate_parameter_value("string", '{"a":1}'))

    def test_non_string_types_are_strictly_validated(self):
        self.assertIsNone(validate_parameter_value("int", "10"))
        self.assertIsNotNone(validate_parameter_value("int", "10.5"))
        self.assertIsNone(validate_parameter_value("float", "10.5"))
        self.assertIsNotNone(validate_parameter_value("bool", "yes"))
        self.assertIsNone(validate_parameter_value("list", '["a"]'))
        self.assertIsNotNone(validate_parameter_value("list", '{"a":1}'))
        self.assertIsNone(validate_parameter_value("object", '{"a":1}'))
        self.assertIsNotNone(validate_parameter_value("object", '["a"]'))

    def test_type_validation_messages_do_not_expose_json_for_list_or_object(self):
        self.assertEqual(validate_parameter_value("list", "t"), "请输入合法的 list 类型")
        self.assertEqual(validate_parameter_value("list", '{"a":1}'), "请输入合法的 list 类型")
        self.assertEqual(validate_parameter_value("object", "t"), "请输入合法的 object 类型")
        self.assertEqual(validate_parameter_value("object", '["a"]'), "请输入合法的 object 类型")

    def test_parameter_item_schema_rejects_value_that_does_not_match_type(self):
        ParameterItemSchema(display_name="JSON 文本", key="jsonText", value='["a"]', type="string")

        with self.assertRaises(ValueError):
            ParameterItemSchema(display_name="数量", key="count", value="1.5", type="int")

        with self.assertRaises(ValueError):
            ParameterItemSchema(display_name="列表", key="ids", value="abc", type="list")

    def test_parameter_set_does_not_allow_duplicate_keys(self):
        items = [
            SimpleNamespace(id=1, key="account_type"),
            SimpleNamespace(id=2, key="account_type"),
        ]

        self.assertTrue(_key_conflicts(items, "account_type", current_item_id=1))
        with self.assertRaises(UnifiedException) as context:
            _ensure_unique_keys(items)
        self.assertEqual(context.exception.code, 400)

    def test_walk_body_candidates_keeps_schema_type_and_path(self):
        body = json.dumps({"user": {"id": 1, "roles": ["admin"]}}, ensure_ascii=False)
        schema_types = {"user.id": "int", "user.roles": "list"}

        candidates = walk_body_candidates(body, schema_types=schema_types, source="interface")

        by_key = {item["key"]: item for item in candidates}
        self.assertEqual(by_key["id"]["type"], "int")
        self.assertEqual(by_key["id"]["type_source"], "schema")
        self.assertEqual(by_key["id"]["field_path"], "body_content_json.user.id")
        self.assertEqual(by_key["roles"]["type"], "list")

    def test_collect_param_candidates_skips_headers_by_default(self):
        candidates = collect_param_candidates(
            source_type="interface",
            source_id=1,
            source_name="GET /users",
            headers=[
                {"key": "Authorization", "value": "Bearer abc", "type": "string", "type_source": "schema"},
                {"key": "X-Tenant", "value": "tenant-a", "type": "string", "type_source": "schema"},
            ],
            query_params=[{"key": "pageSize", "value": "20", "type": "int", "type_source": "schema"}],
            body_content=json.dumps({"userId": 10001}, ensure_ascii=False),
            body_schema_types={"userId": "int"},
        )

        by_key = {item["key"]: item for item in candidates}
        self.assertEqual(by_key["pageSize"]["type"], "int")
        self.assertEqual(by_key["pageSize"]["type_source"], "schema")
        self.assertNotIn("Authorization", by_key)
        self.assertNotIn("X-Tenant", by_key)
        self.assertEqual(by_key["userId"]["field_path"], "body_content_json.userId")

    def test_collect_param_candidates_can_include_non_platform_headers(self):
        candidates = collect_param_candidates(
            source_type="interface",
            source_id=1,
            source_name="GET /users",
            headers=[
                {"key": "Authorization", "value": "Bearer abc", "type": "string", "type_source": "schema"},
                {"key": "X-Tenant", "value": "tenant-a", "type": "string", "type_source": "schema"},
            ],
            include_headers=True,
        )

        by_key = {item["key"]: item for item in candidates}
        self.assertNotIn("Authorization", by_key)
        self.assertEqual(by_key["X-Tenant"]["source_type"], "interface")

    def test_candidate_value_is_classified_against_interface_contract(self):
        self.assertEqual(classify_parameter_candidate("", "int"), "empty")
        self.assertEqual(classify_parameter_candidate("invalid_type", "int"), "invalid")
        self.assertEqual(classify_parameter_candidate("1", "int"), "normal")

    def test_testcase_candidate_inherits_type_from_linked_interface(self):
        interface_candidates = [{
            "key": "account_type",
            "type": "int",
            "type_source": "schema",
            "source_type": "interface",
            "field_path": "query_params.0.value",
        }]
        testcase_candidate = {
            "key": "account_type",
            "type": "string",
            "type_source": "inferred",
            "source_type": "testcase",
            "field_path": "param_overrides.query_params.0.value",
        }

        contract = resolve_parameter_contract(testcase_candidate, interface_candidates)

        self.assertEqual(contract["type"], "int")
        self.assertEqual(contract["type_source"], "schema")

    def test_candidates_with_same_key_are_merged_and_keep_value_variants(self):
        candidates = [
            {
                "key": "account_type", "display_name": "account_type", "value": "",
                "type": "int", "type_source": "schema", "contract_type": "int",
                "source_type": "interface", "source_id": 2247, "source_name": "GET /users",
                "field_path": "query_params.0.value", "match_type": "查询参数 account_type",
                "candidate_status": "empty",
            },
            {
                "key": "account_type", "display_name": "account_type", "value": "",
                "type": "int", "type_source": "schema", "contract_type": "int",
                "source_type": "testcase", "source_id": 3026, "source_name": "基础用例",
                "field_path": "param_overrides.query_params.0.value", "match_type": "查询参数 account_type",
                "candidate_status": "empty",
            },
            {
                "key": "account_type", "display_name": "account_type", "value": "invalid_type",
                "type": "int", "type_source": "schema", "contract_type": "int",
                "source_type": "testcase", "source_id": 3027, "source_name": "非法用例",
                "field_path": "param_overrides.query_params.0.value", "match_type": "查询参数 account_type",
                "candidate_status": "invalid",
            },
        ]

        result = aggregate_parameter_candidates(candidates)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["key"], "account_type")
        self.assertEqual(result[0]["type"], "int")
        self.assertEqual(result[0]["candidate_status"], "invalid")
        self.assertEqual(len(result[0]["sources"]), 3)
        self.assertEqual({source["value"] for source in result[0]["sources"]}, {"", "invalid_type"})

    def test_valid_value_is_preferred_and_invalid_variant_is_not_formal_candidate(self):
        candidates = [
            {
                "key": "account_type", "display_name": "account_type", "value": "1",
                "type": "int", "type_source": "schema", "contract_type": "int",
                "source_type": "interface", "source_id": 2247, "source_name": "GET /users",
                "field_path": "query_params.0.value", "match_type": "查询参数 account_type",
                "candidate_status": "normal",
            },
            {
                "key": "account_type", "display_name": "account_type", "value": "invalid_type",
                "type": "int", "type_source": "schema", "contract_type": "int",
                "source_type": "testcase", "source_id": 3027, "source_name": "非法用例",
                "field_path": "param_overrides.query_params.0.value", "match_type": "查询参数 account_type",
                "candidate_status": "invalid",
            },
        ]

        result = aggregate_parameter_candidates(candidates)

        self.assertEqual(result[0]["candidate_status"], "normal")
        self.assertEqual(result[0]["value"], "1")

    def test_conflicting_interface_types_require_confirmation(self):
        candidates = [
            {"key": "id", "display_name": "id", "value": "1", "type": "int", "type_source": "schema", "contract_type": "int", "source_type": "interface", "source_id": 1, "source_name": "接口A", "field_path": "query_params.0.value", "match_type": "查询参数 id", "candidate_status": "normal"},
            {"key": "id", "display_name": "id", "value": "a-1", "type": "string", "type_source": "schema", "contract_type": "string", "source_type": "interface", "source_id": 2, "source_name": "接口B", "field_path": "query_params.0.value", "match_type": "查询参数 id", "candidate_status": "normal"},
        ]

        result = aggregate_parameter_candidates(candidates)

        self.assertEqual(result[0]["candidate_status"], "type_conflict")
        self.assertEqual(result[0]["type"], "")

    def test_openapi_import_preserves_parameter_and_body_types(self):
        data = {
            "openapi": "3.0.0",
            "paths": {
                "/users/{id}": {
                    "get": {
                        "summary": "Get user",
                        "parameters": [
                            {"name": "id", "in": "path", "schema": {"type": "integer"}},
                            {"name": "active", "in": "query", "schema": {"type": "boolean"}},
                            {"name": "X-Tenant", "in": "header", "schema": {"type": "string"}},
                        ],
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "profile": {
                                                "type": "object",
                                                "properties": {
                                                    "age": {"type": "integer"},
                                                    "tags": {"type": "array", "items": {"type": "string"}},
                                                },
                                            }
                                        },
                                    }
                                }
                            }
                        },
                    }
                }
            },
        }

        result = _parse_openapi(data, "")
        iface = result["modules"][0]["interfaces"][0]

        self.assertEqual(iface["path_params"][0]["type"], "int")
        self.assertEqual(iface["query_params"][0]["type"], "bool")
        self.assertEqual(iface["headers"][0]["type"], "string")
        self.assertEqual(iface["query_params"][0]["type_source"], "schema")
        self.assertEqual(iface["body_schema_types"]["profile.age"], "int")
        self.assertEqual(iface["body_schema_types"]["profile.tags"], "list")


if __name__ == "__main__":
    unittest.main()
