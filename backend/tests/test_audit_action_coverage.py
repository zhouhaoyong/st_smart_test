import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _function_source(relative_path: str, function_name: str) -> str:
    source = _source(relative_path)
    marker = f"async def {function_name}"
    start = source.index(marker)
    next_route = source.find("\n@router.", start + len(marker))
    return source[start:] if next_route < 0 else source[start:next_route]


AUDITED_ACTIONS = {
    "api/v1/endpoints/auth.py": (
        "login_for_access_token",
        "register_user",
        "update_profile",
        "change_password",
        "create_access_token_endpoint",
        "revoke_access_token",
        "logout_user",
    ),
    "api/v1/endpoints/feedbacks.py": (
        "upload_feedback_image",
        "create_feedback",
        "reply_feedback",
        "resolve_feedback",
        "confirm_close_feedback",
        "reopen_feedback",
        "delete_feedback",
    ),
    "api/v1/endpoints/notifications.py": (
        "create_notification_config",
        "update_notification_config",
        "delete_notification_config",
        "test_notification_with_data",
        "test_notification",
    ),
    "api/v1/endpoints/reports.py": (
        "send_report",
        "delete_report",
        "batch_delete_reports",
    ),
    "api/v1/endpoints/import_api.py": ("execute_import",),
    "api/v1/endpoints/executor.py": (
        "upload_temp_file",
        "debug_request",
        "run_test_case",
    ),
    "api/v1/endpoints/collections.py": ("reorder_collections",),
    "api/v1/endpoints/environments.py": (
        "copy_environment",
        "fetch_token_preview",
        "fetch_environment_token",
    ),
    "api/v1/endpoints/executions.py": ("run_execution_set",),
    "api/v1/endpoints/interfaces.py": ("copy_interface",),
    "api/v1/endpoints/projects.py": ("copy_project",),
    "api/v1/endpoints/testcases.py": (
        "copy_test_case",
        "batch_delete_test_cases",
    ),
    "api/v1/endpoints/parameter_sets_routers/items.py": (
        "add_item",
        "batch_add_items",
        "batch_delete_items",
        "update_item",
        "delete_item",
    ),
    "api/v1/endpoints/ai.py": ("api_test_model_billing_draft",),
}


class AuditActionCoverageTests(unittest.TestCase):
    def test_ai_import_module_belongs_to_api_test_group(self):
        source = _source("services/audit_service.py")
        tree = ast.parse(source)
        groups_node = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(getattr(target, "id", None) == "AUDIT_MODULE_GROUPS" for target in node.targets)
        )
        groups = ast.literal_eval(groups_node.value)

        self.assertIn("ai_import", groups["api_test"])
        self.assertNotIn("ai_import", groups["management"])

    def test_confirmed_mutating_actions_call_audit_logger(self):
        for relative_path, functions in AUDITED_ACTIONS.items():
            for function_name in functions:
                with self.subTest(relative_path=relative_path, function_name=function_name):
                    function = _function_source(relative_path, function_name)
                    self.assertTrue(
                        "log_operation(" in function
                        or "log_user_operation(" in function
                        or "log_interface_import(" in function
                        or "_audit_" in function
                    )

    def test_ai_import_workflow_actions_have_business_audit_markers(self):
        source = _source("api/v1/endpoints/import_ai.py")
        for function_name in (
            "ai_import_generate_plan",
            "ai_import_generate",
            "interface_case_generation_save",
            "interface_case_generation_discard",
        ):
            function = _function_source("api/v1/endpoints/import_ai.py", function_name)
            self.assertTrue(
                "log_operation(" in function
                or "log_user_operation(" in function
                or "log_interface_import(" in function
                or "_audit_" in function
            )
        self.assertIn("AI 用例生成已被用户停止", source)

    def test_ai_import_generation_audit_is_emitted_after_all_batches(self):
        source = _source("api/v1/endpoints/import_ai.py")
        start = source.index("async def ai_import_generate(\n")
        next_route = source.find("\n@router.", start)
        function = source[start:] if next_route < 0 else source[start:next_route]
        self.assertIn("if batch_index >= total_batches:", function)
        self.assertIn('"selected"', function)
        self.assertIn('"generated_cases"', function)

    def test_batch_business_actions_write_aggregate_count_audits(self):
        aggregate_functions = {
            "api/v1/endpoints/collections.py": ("batch_delete_collections",),
            "api/v1/endpoints/executions.py": ("batch_delete_execution_sets",),
            "api/v1/endpoints/interfaces.py": ("batch_update_interface_service", "batch_delete_interfaces"),
            "api/v1/endpoints/reports.py": ("batch_delete_reports",),
            "api/v1/endpoints/testcases.py": ("batch_delete_test_cases",),
            "api/v1/endpoints/parameter_sets_routers/sets.py": ("batch_replace",),
        }
        for relative_path, function_names in aggregate_functions.items():
            for function_name in function_names:
                with self.subTest(relative_path=relative_path, function_name=function_name):
                    function = _function_source(relative_path, function_name)
                    self.assertIn("description=", function)
                    self.assertTrue(
                        "build_batch_audit_description" in function
                        or "count" in function
                        or "批量" in function
                    )

    def test_multi_row_create_actions_include_related_counts(self):
        aggregate_functions = {
            "api/v1/endpoints/executions.py": ("create_execution_set", "update_execution_set"),
            "api/v1/endpoints/parameter_sets_routers/sets.py": (
                "create_parameter_set",
                "update_parameter_set",
                "copy_parameter_set",
            ),
        }
        for relative_path, function_names in aggregate_functions.items():
            for function_name in function_names:
                with self.subTest(relative_path=relative_path, function_name=function_name):
                    function = _function_source(relative_path, function_name)
                    self.assertIn("build_batch_audit_description", function)

    def test_environment_service_batch_update_includes_affected_count(self):
        function = _function_source("api/v1/endpoints/environments.py", "update_environment")
        self.assertIn('"service_config" in update_data', function)
        self.assertIn("service_config_count", function)
        self.assertIn("build_batch_audit_description", function)

    def test_login_failure_is_not_audited(self):
        function = _function_source("api/v1/endpoints/auth.py", "login_for_access_token")
        failure_start = function.index("if not verify_password")
        disabled_start = function.index("if not user.is_active", failure_start)
        self.assertNotIn("log_user_operation", function[failure_start:disabled_start])

    def test_audit_content_uses_business_description_and_safe_target(self):
        source = _source("../frontend/src/utils/auditContent.js")
        start = source.index("export const formatAuditContent")
        formatter = source[start:]
        # 操作内容以后端中文描述为准，前端不再拼接「：目标XXX」后缀。
        self.assertIn("cleanAuditText(row?.description)", formatter)
        self.assertIn("if (description) return description", formatter)
        self.assertNotIn("appendAuditTarget", source)
        self.assertIn("formatAuditTarget", source)
        self.assertIn("getOperationName(row?.operation)", formatter)

    def test_api_test_audit_content_has_result_summaries(self):
        source = _source("../frontend/src/utils/auditContent.js")
        for marker in (
            "formatLegacyAiImportContent",
            "formatExecutorContent",
            "recommended_interfaces",
            "generated_cases",
            "total_passed",
            "total_failed",
        ):
                with self.subTest(marker=marker):
                    self.assertIn(marker, source)

    def test_project_scoped_audit_writers_use_project_internal_wording(self):
        audit_logger_source = _source("utils/audit_logger.py")
        workbench_source = _source("api/v1/endpoints/test_workbench_routers/_shared.py")

        self.assertIn("def build_project_audit_description", audit_logger_source)
        self.assertIn("build_project_audit_description", workbench_source)
        self.assertIn("_workbench_project_name", workbench_source)

    def test_executor_audit_uses_execution_counts_and_interface_target(self):
        source = _function_source("api/v1/endpoints/executor.py", "run_test_case")
        self.assertIn("executed_interface_names", source)
        self.assertIn('"execution_count"', source)
        self.assertIn('"successful_executions"', source)
        self.assertIn('"failed_executions"', source)
        self.assertNotIn('"step_count"', source)

    def test_executor_audit_distinguishes_debug_and_case_run(self):
        debug_source = _function_source("api/v1/endpoints/executor.py", "debug_request")
        case_source = _function_source("api/v1/endpoints/executor.py", "run_test_case")
        self.assertIn('operation="接口调试"', debug_source)
        self.assertIn('"execution_type": "interface"', debug_source)
        self.assertIn('operation="用例运行"', case_source)
        self.assertIn('"execution_type": "case"', case_source)
        self.assertIn("test_case_name", case_source)

    def test_execution_audit_content_uses_project_and_result_summary(self):
        from api.v1.endpoints.executions import (
            _build_execution_audit_description,
            _build_execution_result_audit_description,
        )

        report = SimpleNamespace(
            total_cases=120,
            passed_cases=100,
            failed_cases=20,
        )
        self.assertEqual(
            _build_execution_audit_description("订单", "触发执行集", "回归测试集"),
            "订单项目内，触发执行集：回归测试集",
        )
        self.assertEqual(
            _build_execution_result_audit_description("订单", "回归测试集", report),
            "订单项目内，执行集「回归测试集」执行结果：成功100，失败20，未执行0，共计120",
        )

    def test_execution_failure_and_parameter_set_update_audits_use_project_context(self):
        execution_source = _function_source("api/v1/endpoints/executions.py", "run_execution_set")
        parameter_set_source = _function_source(
            "api/v1/endpoints/parameter_sets_routers/sets.py",
            "update_parameter_set",
        )
        self.assertIn("_build_execution_audit_description", execution_source)
        self.assertIn("_build_execution_result_audit_description", execution_source)
        self.assertNotIn("project_internal=False", _source("api/v1/endpoints/executions.py"))
        self.assertIn("build_project_audit_description", parameter_set_source)

    def test_audit_page_renders_confirmed_operation_labels(self):
        source = _source("../frontend/src/utils/auditContent.js")
        for label in (
            "登录", "注册", "退出", "修改密码", "创建令牌", "撤销令牌",
            "提交", "回复", "解决", "确认关闭", "重新打开", "发送",
            "接口调试", "用例运行", "调试", "提取令牌", "设为默认", "排序", "上传", "解析",
            "推荐", "生成", "预览", "转换", "执行",
        ):
            with self.subTest(label=label):
                self.assertTrue(f"'{label}'" in source or f'"{label}"' in source)

    def test_curl_batch_import_is_saved_and_audited_as_one_operation(self):
        source = _source("api/v1/endpoints/import_api.py")
        function = _function_source("api/v1/endpoints/import_api.py", "execute_curl_batch_import")
        self.assertIn('@router.post("/curl-batch")', source)
        self.assertIn("log_interface_import(", function)
        self.assertIn('"new_interfaces"', function)
        self.assertIn('"new_test_cases"', function)
        self.assertNotIn("log_operation(", function)
