import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.v1.endpoints.parameter_sets import (
    _body_matches_for_parameterize,
    _display_name_conflicts,
    _find_references_in_record,
    _pair_matches_for_parameterize,
    _replace_raw_text_for_parameterize,
)
from api.v1.endpoints.parameter_sets_routers import sets as sets_endpoint
from api.v1.endpoints.parameter_sets_routers.sets import (
    BatchReplaceRequest,
    ParameterUpdate,
    _annotate_parameter_matches,
    _candidate_location,
    _normalize_candidate_locations,
)
from services.parameter_reference_service import _replace_json_parameter_references


class ParameterSearchTests(unittest.TestCase):
    def test_candidate_location_filter_defaults_to_common_locations(self):
        self.assertEqual(_normalize_candidate_locations(None, False), {"query", "path", "body"})
        self.assertEqual(_normalize_candidate_locations([], False), set())
        self.assertEqual(_normalize_candidate_locations(["none"], False), set())
        self.assertEqual(_normalize_candidate_locations(["headers"], False), {"headers"})
        self.assertEqual(_normalize_candidate_locations(["all"], False), {"query", "path", "body", "headers"})

    def test_candidate_location_maps_interface_and_testcase_field_paths(self):
        self.assertEqual(_candidate_location("query_params.0.value"), "query")
        self.assertEqual(_candidate_location("param_overrides.path_params.0.value"), "path")
        self.assertEqual(_candidate_location("body_content_json.user_id"), "body")
        self.assertEqual(_candidate_location("param_overrides.headers.0.value"), "headers")

    def test_batch_replace_accepts_parameter_value_and_type_updates(self):
        request = BatchReplaceRequest(
            parameter_set_id=3,
            parameter_updates=[ParameterUpdate(id=12, value="100", type="int")],
        )

        self.assertEqual(request.parameter_set_id, 3)
        self.assertEqual(request.parameter_updates[0].model_dump(), {"id": 12, "value": "100", "type": "int"})

    def test_body_match_with_key_does_not_return_raw_body_substring_match(self):
        body = '{\n  "nick_name": {},\n  "gender": 3,\n  "department": 1\n}'

        matches = _body_matches_for_parameterize(body, "1", "project_id", "body_content")

        self.assertEqual(matches, [])

    def test_body_match_with_key_returns_exact_json_field_even_when_value_matches(self):
        body = '{"project_id": 1, "department": 1}'

        matches = _body_matches_for_parameterize(body, "1", "project_id", "body_content")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["path"], "body_content_json.project_id")
        self.assertEqual(matches[0]["value"], "1")

    def test_body_match_with_key_reports_type_mismatch_for_object_value(self):
        body = '{"test1": {"name": "zhy"}}'

        matches = _body_matches_for_parameterize(body, "测试", "test1", "body_content", param_type="string")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["path"], "body_content_json.test1")
        self.assertEqual(matches[0]["value"], '{"name": "zhy"}')
        self.assertEqual(matches[0]["actual_type"], "object")
        self.assertEqual(matches[0]["expected_type"], "string")
        self.assertIn("类型不匹配", matches[0]["conflict_reason"])

    def test_body_match_uses_schema_type_for_empty_object_placeholder(self):
        body = '{"name": {}}'

        matches = _body_matches_for_parameterize(
            body,
            "zhy",
            "name",
            "body_content",
            param_type="string",
            schema_types={"name": "string"},
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["path"], "body_content_json.name")
        self.assertEqual(matches[0]["actual_type"], "string")
        self.assertEqual(matches[0]["expected_type"], "string")
        self.assertNotIn("conflict_reason", matches[0])

    def test_body_match_without_schema_reports_object_type_mismatch(self):
        body = '{"name": {}}'

        matches = _body_matches_for_parameterize(body, "zhy", "name", "body_content", param_type="string")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["actual_type"], "object")
        self.assertIn("conflict_reason", matches[0])

    def test_body_match_without_key_can_still_find_raw_body_text(self):
        body = '{"token": "abc123"}'

        matches = _body_matches_for_parameterize(body, "abc123", None, "body_content")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["path"], "body_content")

    def test_pair_match_with_key_does_not_match_other_values(self):
        self.assertTrue(_pair_matches_for_parameterize("name", "zhangsan", "zhangsan", "name"))
        self.assertFalse(_pair_matches_for_parameterize("nickname", "zhangsan-old", "zhangsan", "name"))

    def test_pair_match_without_key_can_still_find_value(self):
        self.assertTrue(_pair_matches_for_parameterize("nickname", "zhangsan-old", "zhangsan", None))

    def test_same_key_with_different_value_is_marked_as_conflict(self):
        matches = [{
            "field": "body_content_json.action",
            "path": "body_content_json.action",
            "key": "action",
            "value": "decode",
            "match_type": "请求体字段 action",
        }]

        _annotate_parameter_matches(matches, "encode", "string")

        self.assertFalse(matches[0]["value_matches"])
        self.assertEqual(matches[0]["conflict_kind"], "value_mismatch")
        self.assertIn("值不同", matches[0]["conflict_reason"])

    def test_raw_body_replace_ignores_empty_search_value(self):
        body = '{"password": "<password>"}'

        self.assertEqual(_replace_raw_text_for_parameterize(body, "", "$.test1"), body)

    def test_raw_body_replace_uses_original_search_value(self):
        body = '{"token": "abc123"}'

        self.assertEqual(_replace_raw_text_for_parameterize(body, "abc123", "$.token"), '{"token": "$.token"}')

    def test_json_reference_restore_keeps_bool_type(self):
        restored, changed = _replace_json_parameter_references(
            '{"remember_me":"$.remember_me"}', "remember_me", "false", "bool"
        )

        self.assertTrue(changed)
        self.assertEqual(restored, '{\n  "remember_me": false\n}')

    def test_display_name_conflict_ignores_current_item(self):
        items = [
            SimpleNamespace(id=1, display_name="项目 ID"),
            SimpleNamespace(id=2, display_name="用户"),
        ]

        self.assertTrue(_display_name_conflicts(items, " 项目 ID "))
        self.assertFalse(_display_name_conflicts(items, " 项目 ID ", current_item_id=1))

    def test_find_references_in_interface_record(self):
        iface = SimpleNamespace(
            id=10,
            method="GET",
            url="/projects/{project_id}",
            name="Get Project",
            headers=[{"key": "X-Project", "value": "$.project_id"}],
            query_params=[{"key": "project_id", "value": "$.project_id"}],
            path_params=[{"key": "project_id", "value": "$.project_id"}],
            body_content='{"project_id":"$.project_id"}',
        )

        refs = _find_references_in_record("interface", iface, "project_id")

        self.assertGreaterEqual(len(refs), 4)
        self.assertEqual(refs[0]["source_type"], "interface")
        self.assertEqual(refs[0]["source_id"], 10)
        self.assertTrue(any(ref["field_path"] == "query_params.0.value" for ref in refs))

    def test_find_references_in_test_case_record(self):
        tc = SimpleNamespace(
            id=20,
            name="Get Project Case",
            param_overrides={
                "headers": [{"key": "X-Project", "value": "$.project_id"}],
                "query_params": [{"key": "project_id", "value": "{{project_id}}"}],
                "path_params": [{"key": "project_id", "value": "$.project_id"}],
                "body_content": '{"project_id":"$.project_id"}',
            },
        )

        refs = _find_references_in_record("testcase", tc, "project_id")

        self.assertGreaterEqual(len(refs), 4)
        self.assertEqual(refs[0]["source_type"], "testcase")
        self.assertTrue(any(ref["field_path"] == "param_overrides.query_params.0.value" for ref in refs))


class _SearchResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _SearchDb:
    def __init__(self, interface, testcase):
        self.results = [_SearchResult([interface]), _SearchResult([testcase])]

    async def execute(self, _statement):
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_search_values_returns_interface_metadata_and_filters_case_name():
    interface = SimpleNamespace(
        id=10,
        name="用户详情",
        method="GET",
        url="/api/users/{user_id}",
        body_content='{"user_id":1001}',
        body_schema_types={},
        headers=[],
        query_params=[],
        path_params=[],
    )
    testcase = SimpleNamespace(
        id=20,
        name="登录用例",
        project_id=8,
        interface_id=10,
        interface=interface,
        param_overrides={"body_content": '{"user_id":1001}'},
    )
    db = _SearchDb(interface, testcase)
    current_user = SimpleNamespace(is_manager=True, is_superuser=False)

    with patch.object(sets_endpoint, "_ensure_project_access_permission", new=AsyncMock()):
        response = await sets_endpoint.search_values(
            project_id=8,
            search_value="1001",
            match_key="user_id",
            param_type="int",
            include_headers=False,
            source_keyword="登录",
            current_user=current_user,
            db=db,
        )

    assert response["data"]["total"] == 1
    assert response["data"]["results"][0]["type"] == "testcase"
    assert response["data"]["results"][0]["interface_id"] == 10
    assert response["data"]["results"][0]["interface_url"] == "/api/users/{user_id}"


@pytest.mark.asyncio
async def test_detect_candidates_with_no_locations_returns_empty_without_scanning():
    current_user = SimpleNamespace(is_manager=True, is_superuser=False)

    with patch.object(sets_endpoint, "_ensure_project_access_permission", new=AsyncMock()):
        response = await sets_endpoint.detect_candidates(
            project_id=8,
            include_headers=False,
            keyword=None,
            locations=[],
            current_user=current_user,
            db=SimpleNamespace(),
        )

    assert response["data"] == {"items": [], "total": 0}


if __name__ == "__main__":
    unittest.main()
