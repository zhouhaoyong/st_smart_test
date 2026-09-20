import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.v1.endpoints.executions import ExecutionSetCreate
from core.permissions import can_view_project_details
from services.collection_tree import would_create_collection_cycle
from services.execution_engine.assertions import run_assertions
from services.schedule_runner import resolve_schedule_execution_status


def user(user_id=1, *, manager=False, superuser=False):
    return SimpleNamespace(id=user_id, is_manager=manager, is_superuser=superuser)


def project(owner_id=1, *, public=False):
    return SimpleNamespace(owner_id=owner_id, is_public=public)


class ConfirmedBehaviorFixTests(unittest.TestCase):
    def test_business_code_assertion_accepts_number_and_string_200_but_rejects_missing_code(self):
        assertion = [{
            "type": "jsonpath",
            "expression": "$.code",
            "operator": "eq",
            "expected": "200",
            "enabled": True,
        }]

        self.assertEqual(run_assertions(assertion, {"json": {"code": 200}}, 1, [])[1], 0)
        self.assertEqual(run_assertions(assertion, {"json": {"code": "200"}}, 1, [])[1], 0)
        self.assertEqual(run_assertions(assertion, {"json": {"message": "ok"}}, 1, [])[1], 1)
        self.assertEqual(run_assertions(assertion, {"json": None}, 1, [])[1], 1)

    def test_disabled_business_code_assertion_is_not_evaluated(self):
        disabled = [{
            "type": "jsonpath",
            "expression": "$.code",
            "operator": "eq",
            "expected": "200",
            "enabled": False,
        }]

        self.assertEqual(run_assertions(disabled, {"json": {"code": 500}}, 1, [])[0], 0)
        self.assertEqual(run_assertions(disabled, {"json": {"code": 500}}, 1, [])[1], 0)

    def test_not_empty_operator_rejects_null_and_empty_values(self):
        assertion = [{
            "type": "jsonpath",
            "expression": "$.data",
            "operator": "not_empty",
            "expected": "",
            "enabled": True,
        }]

        # 有值：通过（0 和 false 也算有值）
        self.assertEqual(run_assertions(assertion, {"json": {"data": {"id": 1}}}, 1, [])[0], 1)
        self.assertEqual(run_assertions(assertion, {"json": {"data": [1]}}, 1, [])[0], 1)
        self.assertEqual(run_assertions(assertion, {"json": {"data": 0}}, 1, [])[0], 1)
        self.assertEqual(run_assertions(assertion, {"json": {"data": False}}, 1, [])[0], 1)
        # 空值：不通过
        self.assertEqual(run_assertions(assertion, {"json": {"data": None}}, 1, [])[1], 1)
        self.assertEqual(run_assertions(assertion, {"json": {"data": ""}}, 1, [])[1], 1)
        self.assertEqual(run_assertions(assertion, {"json": {"data": []}}, 1, [])[1], 1)
        self.assertEqual(run_assertions(assertion, {"json": {"data": {}}}, 1, [])[1], 1)
        self.assertEqual(run_assertions(assertion, {"json": {"message": "ok"}}, 1, [])[1], 1)

    def test_blank_assertion_expression_fails_without_breaking_run(self):
        """表达式为空的断言按失败处理，不影响整轮执行"""
        assertion = [{
            "type": "jsonpath",
            "expression": "",
            "operator": "eq",
            "expected": "",
            "enabled": True,
        }]

        passed, failed, diffs = run_assertions(assertion, {"json": {"code": 200}}, 1, [])
        self.assertEqual((passed, failed), (0, 1))
        self.assertEqual(diffs[0]["result"], "fail")

    def test_dollar_expression_reads_whole_response_body(self):
        assertion = [{
            "type": "jsonpath",
            "expression": "$",
            "operator": "not_empty",
            "expected": "",
            "enabled": True,
        }]

        self.assertEqual(run_assertions(assertion, {"json": {"code": 200}}, 1, [])[0], 1)
        self.assertEqual(run_assertions(assertion, {"json": {}}, 1, [])[1], 1)

    def test_collection_parent_validation_rejects_self_and_descendant_parent(self):
        parent_map = {1: None, 2: 1, 3: 2, 4: 1}

        self.assertTrue(would_create_collection_cycle(2, 2, parent_map))
        self.assertTrue(would_create_collection_cycle(1, 3, parent_map))
        self.assertFalse(would_create_collection_cycle(3, 4, parent_map))

    def test_retry_count_allows_three_and_rejects_four_and_negative(self):
        base = {"name": "回归执行", "project_id": 1, "environment_id": 1}
        self.assertEqual(ExecutionSetCreate(**base, retry_count=3).retry_count, 3)
        with self.assertRaises(ValidationError):
            ExecutionSetCreate(**base, retry_count=4)
        with self.assertRaises(ValidationError):
            ExecutionSetCreate(**base, retry_count=-1)

    def test_schedule_status_follows_report_status(self):
        self.assertEqual(resolve_schedule_execution_status("success"), "success")
        self.assertEqual(resolve_schedule_execution_status("failed"), "failed")
        self.assertEqual(resolve_schedule_execution_status("error"), "failed")

    def test_detail_access_is_limited_to_owner_or_manager(self):
        public_project = project(owner_id=1, public=True)

        self.assertTrue(can_view_project_details(user(1), public_project))
        self.assertTrue(can_view_project_details(user(2, manager=True), public_project))
        self.assertTrue(can_view_project_details(user(2, superuser=True), public_project))
        self.assertFalse(can_view_project_details(user(2), public_project))


if __name__ == "__main__":
    unittest.main()
