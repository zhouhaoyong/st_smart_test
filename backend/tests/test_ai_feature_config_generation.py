import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.test_workbench_audit import build_change_details, soft_delete_workbench_record


def _literal_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"未找到配置项：{name}")


def test_test_case_generation_uses_streaming_call_and_exposes_its_model():
    endpoint_file = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py"
    endpoint = endpoint_file.read_text(encoding="utf-8")

    assert '"/test-cases/ai-model"' in endpoint
    assert 'feature="test_workbench_test_case_generate"' in endpoint
    assert "stream_callback=" in endpoint


def test_test_case_generation_dialog_owns_model_and_error_feedback():
    api_file = ROOT.parent / "frontend" / "src" / "api" / "testWorkbench.js"
    dialog_file = ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "TestCaseGenerateDialog.vue"
    api = api_file.read_text(encoding="utf-8")
    dialog = dialog_file.read_text(encoding="utf-8")
    message_card = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RefinementMessageCard.vue").read_text(encoding="utf-8")

    assert "getWorkbenchTestCaseAiModel" in api
    assert "skipErrorToast: true" in api
    assert "<el-steps" in dialog
    assert "modelInfo" in dialog
    assert "<RefinementMessageCard" in dialog
    assert ":retry-selection-required=\"retrySelectionRequired\"" in dialog
    assert "error-actions" in message_card


def test_multi_requirement_case_generation_uses_the_long_ai_request_timeout():
    api_file = ROOT.parent / "frontend" / "src" / "api" / "testWorkbench.js"
    api = api_file.read_text(encoding="utf-8")

    assert "generateWorkbenchTestCases = (data)" in api
    assert "timeout: 600000" in api


def test_test_case_generation_is_audited_after_model_response():
    endpoint_file = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py"
    endpoint = endpoint_file.read_text(encoding="utf-8")
    ai_service = "".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "services" / "ai_service").glob("*.py")
    )

    assert 'audit_action="tw_test_case_generate"' in endpoint
    assert 'operation="AI生成", asset_name="测试用例"' in endpoint
    assert "_log_ai_usage_immediate" in ai_service
    assert "reserve_ai_quota_slot" not in ai_service


def test_test_case_list_keeps_bulk_actions_in_query_row_and_deletes_current_list_scope():
    list_file = ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue"
    source = list_file.read_text(encoding="utf-8")

    assert "批量删除" in source
    assert "全部删除" in source
    assert "deleteAllCurrentCases" in source
    assert "currentListDeletePayload" in source
    assert "case-selection-actions" not in source


def test_test_case_generation_loading_uses_rotating_copy_without_large_decorative_icon():
    dialog_file = ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "TestCaseGenerateDialog.vue"
    source = dialog_file.read_text(encoding="utf-8")

    assert "v-if=\"streaming\"" in source
    assert "AiStopStreamButton" in source
    assert "statusLabel" in source
    assert "MagicStick" not in source


def test_ai_json_parser_repairs_a_chinese_quote_used_as_a_string_terminator():
    from services.ai_service import _robust_json_parse

    raw = '{"test_cases":[{"test_data":{"当前用户":"普通用户A”， "操作":"查看权限"}}]}'

    parsed = _robust_json_parse(raw)

    assert parsed == {
        "test_cases": [{"test_data": {"当前用户": "普通用户A", "操作": "查看权限"}}],
    }


def test_ai_json_parser_repairs_missing_property_value():
    from services.ai_service import _robust_json_parse

    raw = '{"test_cases":[{"title":"权限校验","test_data":{"资源":,"角色":"普通用户"},"steps":[]}]}'

    parsed = _robust_json_parse(raw)

    assert parsed == {
        "test_cases": [{
            "title": "权限校验",
            "test_data": {"资源": None, "角色": "普通用户"},
            "steps": [],
        }],
    }


def test_test_case_schema_normalizes_string_steps_before_batch_save():
    from schemas.test_workbench import TWTestCaseCreate, TWTestCaseUpdate

    case = TWTestCaseCreate(
        project_id=1,
        system_id=1,
        version_id=1,
        title="普通用户提交需求",
        steps_json=["打开需求页面", {"step": "填写并提交"}, "查看提交结果"],
    )

    assert case.steps_json == [
        {"step": "打开需求页面"},
        {"step": "填写并提交"},
        {"step": "查看提交结果"},
    ]
    assert TWTestCaseUpdate(steps_json=None).steps_json is None


def test_case_preview_normalizes_steps_before_saving():
    dialog = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "TestCaseGenerateDialog.vue").read_text(encoding="utf-8")

    assert "const normalizeSteps" in dialog
    assert "steps_json: normalizeSteps" in dialog


def test_test_case_generation_prompt_compacts_content_without_case_count_limit():
    prompt = (ROOT / "docs" / "prompt" / "test_workbench_test_case_generation.md").read_text(encoding="utf-8")

    assert "最多生成 12 条" not in prompt
    assert "标题不超过 30 个中文字符" in prompt


def test_test_case_generation_handles_each_selected_requirement_independently():
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")

    assert "required_calls = len(sources)" in endpoint
    assert "for source in sources:" in endpoint
    assert '"requirements": [source]' in endpoint
    assert 'selected_model_id=data.selected_model_id' in endpoint


def test_test_case_generation_checks_each_selected_model_call_with_the_current_quota_rule():
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")

    # 每条来源需求对应一次模型调用，额度校验统一在模型路由层完成，接口不再提前做旧的总量拦截。
    assert "check_user_ai_quota" not in endpoint
    assert "call_ai_for_feature(" in endpoint
    assert "selected_model_id=data.selected_model_id" in endpoint


def test_test_case_generation_keeps_all_cases_and_compacts_each_case():
    prompt = (ROOT / "docs" / "prompt" / "test_workbench_test_case_generation.md").read_text(encoding="utf-8")

    assert "最多生成 12 条" not in prompt
    assert "标题不超过 30 个中文字符" in prompt
    assert "步骤不超过 5 步" in prompt


def test_ai_case_preview_links_sources_and_uses_one_detail_edit_dialog():
    preview = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "TestCaseGenerateDialog.vue").read_text(encoding="utf-8")
    case_list = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue").read_text(encoding="utf-8")

    assert "openSourceRequirement" in preview
    assert "source_title" in preview
    assert "source_ref" in preview
    assert 'label="用例编号"' not in preview
    assert "previewCaseDialog.editing" in preview
    assert "编辑用例" in preview
    assert "@click=\"openPreviewCase(row)\"" in preview
    assert "case_no', label: '用例编号'" in case_list
    assert "优先级" in case_list
    assert "用例类型" in case_list
    assert "priority: '', case_type: ''" in case_list
    assert "priority: filters.priority" in case_list
    assert "case_type: filters.case_type" in case_list
    assert "minWidth: 240" in case_list


def test_test_case_filters_are_applied_by_the_backend_for_lists_and_bulk_actions():
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")
    service = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "services" / "test_workbench_service").glob("*.py")))
    route = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "structure.py").read_text(encoding="utf-8")
    batch_route = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")

    assert "priority: str | None = None" in schema
    assert "case_type: str | None = None" in schema
    assert "TWTestCase.priority == priority" in service
    assert "TWTestCase.case_type == case_type" in service
    assert "priority: str | None = Query" in route
    assert "case_type: str | None = Query" in route
    assert "priority=data.priority" in batch_route
    assert "case_type=data.case_type" in batch_route


def test_pending_bug_severity_is_chinese_and_pending_navigation_is_last():
    workbench = (ROOT.parent / "frontend" / "src" / "views" / "TestWorkbench.vue").read_text(encoding="utf-8")
    pending_page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "pages" / "WorkbenchPendingPage.vue").read_text(encoding="utf-8")
    pending_list = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchPendingList.vue").read_text(encoding="utf-8")

    assert "format: 'severity'" in pending_page
    assert "major: '主要'" in pending_list
    assert workbench.index("key: 'pending'") > workbench.index("key: 'legacy'")


def test_long_heading_requirement_is_split_without_cutting_unstructured_text():
    from services.test_workbench_service import split_requirement_for_generation

    short = "# 登录\n登录后进入首页"
    long_unstructured = "需求说明" * 4000
    long_structured = "\n".join([
        "# 账户管理",
        "账号规则" * 1600,
        "## 权限控制",
        "权限规则" * 1600,
    ])

    assert split_requirement_for_generation(short) == [short]
    assert split_requirement_for_generation(long_unstructured) == [long_unstructured]
    assert len(split_requirement_for_generation(long_structured)) >= 2


def test_test_case_generation_supports_completed_requirements_and_persists_the_exact_source():
    model = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "models").glob("models_*.py")))
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")

    assert "completed_requirement_id" in model
    assert "completed_requirement_id: int | None = None" in schema
    assert '"completed_requirement"' in endpoint
    assert "completed_requirement_id" in endpoint


def test_case_number_allocator_uses_the_system_and_version_scope():
    from services.test_workbench_service import allocate_scoped_case_no_strings

    assert allocate_scoped_case_no_strings({"TC-PORTAL-V120-00009", "manual-01"}, "Portal", "v1.2.0", 2) == [
        "TC-PORTAL-V120-00010",
        "TC-PORTAL-V120-00011",
    ]


def test_draft_case_list_supports_confirming_every_filtered_case_in_scope():
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")
    page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue").read_text(encoding="utf-8")

    assert "confirm_all_in_scope" in schema
    assert "confirm_all_in_scope" in endpoint
    assert "全部确认" in page


def test_test_case_confirmation_tabs_keep_operations_in_their_allowed_statuses():
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")
    api = (ROOT.parent / "frontend" / "src" / "api" / "testWorkbench.js").read_text(encoding="utf-8")
    page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue").read_text(encoding="utf-8")

    assert '@router.post("/test-cases/batch-cancel-confirm")' in endpoint
    assert "batchCancelConfirmWorkbenchTestCases" in api
    assert "selectedDraftCases" in page and "selectedConfirmedCases" in page
    assert "caseTypeOptions" in page and "功能测试" in page
    assert "confirmWorkbenchTestCase" in page
    assert 'v-if="confirmTab === \'draft\'" link type="primary" @click="confirmCase(row)"' in page
    assert "confirm_status != \"draft\"" in endpoint
    assert "confirm_status != \"confirmed\"" in endpoint
    assert "confirm_all_in_scope" in schema


def test_project_scope_and_test_case_source_selection_use_remote_cascading_queries():
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")
    requirement_endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py").read_text(encoding="utf-8")
    test_case_endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")
    api = (ROOT.parent / "frontend" / "src" / "api" / "testWorkbench.js").read_text(encoding="utf-8")
    workbench = (ROOT.parent / "frontend" / "src" / "views" / "TestWorkbench.vue").read_text(encoding="utf-8")
    generate_dialog = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "TestCaseGenerateDialog.vue").read_text(encoding="utf-8")

    assert "class TWTestCaseGenerateScope" in schema
    assert "project_id: int" in schema
    assert '@router.get("/projects/{project_id}/test-case-sources")' in requirement_endpoint
    assert "system_ids: list[int]" in requirement_endpoint
    assert "version_ids: list[int]" in requirement_endpoint
    assert "keyword: str | None" in requirement_endpoint
    assert "不在当前项目筛选范围内" in test_case_endpoint
    assert "getWorkbenchTestCaseSources" in api
    assert "WorkbenchScopeSelectorDialog" in workbench
    assert "TestCaseSourceSelector" in generate_dialog
    source_selector = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "TestCaseSourceSelector.vue").read_text(encoding="utf-8")
    scope_selector = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchScopeSelectorDialog.vue").read_text(encoding="utf-8")
    assert "await nextTick()" in source_selector
    assert 'title="选择工作范围"' in scope_selector
    assert "系统 {{ selectedSystemCount }}/{{ projectSystemTotal }}" in scope_selector
    assert "版本 {{ selectedVersionCount }}/{{ projectVersionTotal }}" in scope_selector
    assert "筛选和翻页不会清空已选范围" in scope_selector


def test_ai_test_case_source_query_requires_system_and_version_scope():
    requirement_endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py").read_text(encoding="utf-8")

    assert "_append_test_case_source_scope_conditions" in requirement_endpoint
    assert "system_ids: list[int] = Query(default=[])" in requirement_endpoint
    assert "version_ids: list[int] = Query(default=[])" in requirement_endpoint
    assert "model.system_id.in_(normalized_system_ids)" in requirement_endpoint
    assert "model.version_id.in_(normalized_version_ids)" in requirement_endpoint
    assert "conditions.append(false())" in requirement_endpoint


def test_new_test_cases_use_only_functional_and_nonfunctional_top_level_types():
    prompt = (ROOT / "docs" / "prompt" / "test_workbench_test_case_generation.md").read_text(encoding="utf-8")
    page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue").read_text(encoding="utf-8")

    assert "功能测试" in prompt and "非功能测试" in prompt
    assert "['功能测试', '非功能测试']" in page


def test_test_case_preflight_collects_key_gaps_once_before_generation():
    prompt = (ROOT / "docs" / "prompt" / "test_workbench_test_case_preflight.md").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")
    dialog = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "TestCaseGenerateDialog.vue").read_text(encoding="utf-8")

    assert "首轮 `round=0` 一次性问全所有可识别的关键疑点" in prompt
    assert 'kind="test_case"' in endpoint
    assert 'preflight_completed' in endpoint
    assert '用例预检' in dialog
    assert 'requirement-analyses' not in dialog


def test_test_case_generation_prompt_requires_functional_coverage_and_balanced_priorities():
    prompt = (ROOT / "docs" / "prompt" / "test_workbench_test_case_generation.md").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")

    assert "quality-policy:function-first-balanced-priority" in prompt
    assert all(level in prompt for level in ("P0", "P1", "P2", "P3"))
    assert "no-mechanical-all-P2" in prompt
    assert '"generation_prompt_preview"' in endpoint
    assert '"quality_summary"' in endpoint


def test_test_case_execution_keeps_only_pass_fail_and_not_executed_statuses():
    from core.response import UnifiedException
    from services.test_workbench_service import execution_result_details

    assert execution_result_details("passed") is None
    assert execution_result_details("failed") is None
    assert execution_result_details("not_executed") is None
    with pytest.raises(UnifiedException, match="执行结果不合法"):
        execution_result_details("blocked")


def test_case_list_supports_batch_execution_with_a_case_detail_execution_dialog():
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py").read_text(encoding="utf-8")
    api = (ROOT.parent / "frontend" / "src" / "api" / "testWorkbench.js").read_text(encoding="utf-8")
    list_page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue").read_text(encoding="utf-8")
    execution_dialog = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchExecutionDialog.vue").read_text(encoding="utf-8")

    assert "TWTestCaseBatchExecute" in schema
    assert '@router.post("/test-cases/batch-execute")' in endpoint
    assert "batchExecuteWorkbenchTestCases" in api
    assert "批量执行" in list_page
    assert "AI 生成（AI补全需求）" in list_page
    assert "AI 生成（AI合并需求）" in list_page
    assert "查看详情" not in list_page
    assert 'label="用例详情"' in execution_dialog
    assert 'label="执行记录"' in execution_dialog


def test_case_generation_uses_the_shared_streaming_status_layout():
    dialog = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "TestCaseGenerateDialog.vue").read_text(encoding="utf-8")

    assert 'class="ai-status"' in dialog
    assert 'class="ai-status-tag"' in dialog
    assert 'class="stream-action-bar"' in dialog


def test_test_case_workspace_uses_a_concise_list_and_a_shared_detail_history_layout():
    list_page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue").read_text(encoding="utf-8")
    form_dialog = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetFormDialog.vue").read_text(encoding="utf-8")
    case_config = list_page.split("test_case:", 1)[1].split("bug:", 1)[0]

    assert "{ prop: 'creator_name', label: '创建人'" in case_config
    assert "{ prop: 'requirement_title', label: '关联需求'" not in case_config
    assert "{ prop: 'source_type', label: '来源'" not in case_config
    assert "{ prop: 'confirm_status', label: '确认状态'" not in case_config
    assert "format: 'execution_tag'" in case_config
    assert 'label="用例详情" name="detail"' in form_dialog
    assert 'label="执行记录" name="history"' in form_dialog
    assert 'readonly placeholder="系统自动分配"' in form_dialog


def test_case_no_uses_system_abbreviation_version_and_five_digit_sequence():
    from services.test_workbench_service import allocate_scoped_case_no_strings

    assert allocate_scoped_case_no_strings({"TC-智测-V001-00009"}, "智测", "v0.0.1", 2) == [
        "TC-智测-V001-00010",
        "TC-智测-V001-00011",
    ]


def test_bug_forms_use_chinese_display_assignee_and_an_inline_failed_execution_decision():
    list_page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue").read_text(encoding="utf-8")
    asset_form = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetFormDialog.vue").read_text(encoding="utf-8")
    bug_dialog = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchBugDialog.vue").read_text(encoding="utf-8")
    execution_dialog = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchExecutionDialog.vue").read_text(encoding="utf-8")
    workbench = (ROOT.parent / "frontend" / "src" / "views" / "TestWorkbench.vue").read_text(encoding="utf-8")

    assert "major: '主要'" in list_page
    assert "format: 'severity'" in list_page
    assert 'class="bug-editor-grid"' in asset_form
    assert 'label="指派人"' in asset_form
    assert 'class="bug-form-grid"' in bug_dialog
    assert '是否提交 Bug' in execution_dialog
    assert "form.submit_bug" in execution_dialog
    assert "submitBugAfterFailure" in workbench


def test_pending_workspace_separates_my_repair_verification_and_history():
    model = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "models").glob("models_*.py")))
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "bugs.py").read_text(encoding="utf-8")
    service = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "services" / "test_workbench_service").glob("*.py")))
    pending_page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "pages" / "WorkbenchPendingPage.vue").read_text(encoding="utf-8")
    pending_list = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchPendingList.vue").read_text(encoding="utf-8")

    assert "verifier_id" in model
    bug_create_schema = schema[schema.index("class TWBugCreate"):schema.index("class TWBugUpdate")]
    assert "verifier_id" not in bug_create_schema
    assert 'bug_data["verifier_id"] = current_user.id' in endpoint
    assert "can_operate_bug_workflow" in endpoint
    assert 'TWBugTransition.action.in_(("resolve", "verify", "reactivate"))' in service
    assert "待我处理" in pending_page
    assert "待我验证" in pending_page
    assert "我处理过" in pending_page
    assert "openDetail" in pending_list
    assert "提交修复" in pending_list
    assert "提交验证" in pending_list
