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


def _function_source(relative_path: str, function_name: str) -> str:
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    marker = f"async def {function_name}"
    start = source.index(marker)
    next_route = source.find("\n@router.", start + len(marker))
    return source[start:] if next_route < 0 else source[start:next_route]


def _literal_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"未找到配置项：{name}")


def test_workbench_audit_only_keeps_changed_business_fields():
    before = {"name": "登录系统", "description": "旧说明", "updated_at": datetime(2026, 7, 23, 10, 0, 0)}
    after = {"name": "登录系统", "description": "新说明", "updated_at": datetime(2026, 7, 23, 10, 1, 0)}

    assert build_change_details(before, after) == {
        "before": {"description": "旧说明"},
        "after": {"description": "新说明"},
    }


def test_soft_delete_workbench_record_preserves_record_and_marks_actor():
    record = SimpleNamespace(is_deleted=False, deleted_at=None, updated_by=None)
    deleted_at = datetime(2026, 7, 23, 10, 0, 0)

    soft_delete_workbench_record(record, user_id=7, deleted_at=deleted_at)

    assert record.is_deleted is True
    assert record.deleted_at == deleted_at
    assert record.updated_by == 7


def test_workbench_batch_mutations_use_one_aggregate_audit_record():
    cases = {
        "api/v1/endpoints/test_workbench_routers/requirements.py": (
            "batch_delete_requirements",
            "batch_confirm_requirements",
            "batch_delete_completed_requirements",
            "batch_confirm_completed_requirements",
        ),
        "api/v1/endpoints/test_workbench_routers/test_cases.py": (
            "batch_create_test_cases",
            "batch_confirm_test_cases",
            "batch_cancel_confirm_test_cases",
            "batch_delete_test_cases",
            "batch_execute_test_cases",
        ),
        "api/v1/endpoints/test_workbench_routers/bugs.py": ("batch_delete_bugs",),
        "api/v1/endpoints/test_workbench_routers/merged.py": ("batch_confirm_merged_requirements",),
    }

    for relative_path, function_names in cases.items():
        for function_name in function_names:
            function = _function_source(relative_path, function_name)
            assert "_audit_workbench_batch_mutation" in function
            assert "_audit_workbench_mutation(" not in function

    generation = _function_source(
        "api/v1/endpoints/test_workbench_routers/test_cases.py",
        "generate_test_cases",
    )
    assert generation.count("_audit_workbench_ai_operation(") == 1
    assert "_audit_workbench_mutation(" not in generation


def test_requirement_refinement_waits_for_user_confirmation_before_first_call():
    # 确认页已抽成 RefinementStartConfirm，状态机在 useRequirementRefinement 里。
    drawer = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementRefinementDrawer.vue").read_text(encoding="utf-8")
    start_confirm = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RefinementStartConfirm.vue").read_text(encoding="utf-8")
    composable = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "composables" / "useRequirementRefinement.js").read_text(encoding="utf-8")

    assert "开始 AI 补全" in start_confirm
    assert "<RefinementStartConfirm" in drawer
    assert "@start=\"start\"" in drawer
    assert "const start = async () =>" in composable
    # 每次打开对话框都重置本次会话，不回放历史
    assert "const open = async () => {\n    reset()" in composable


def test_requirement_refinement_is_centered_and_keeps_local_assistant_result():
    drawer = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementRefinementDrawer.vue").read_text(encoding="utf-8")
    start_confirm = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RefinementStartConfirm.vue").read_text(encoding="utf-8")
    card = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RefinementMessageCard.vue").read_text(encoding="utf-8")

    assert "<el-dialog" in drawer
    assert "开始 AI 补全" in start_confirm
    # 助手结果留在本次会话中，可复制、可查看思考过程
    assert "<RefinementMessageCard" in drawer
    assert "复制" in card
    assert "思考过程" in card


def test_workbench_assets_can_maintain_and_show_requirement_traceability():
    schema_file = ROOT / "schemas" / "test_workbench.py"
    service_file = ROOT / "services" / "test_workbench_service"
    form_file = ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetFormDialog.vue"
    list_file = ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "WorkbenchAssetListPage.vue"

    schema = schema_file.read_text(encoding="utf-8")
    assert schema.count("requirement_id: int | None = None") >= 5
    assert "requirement_title" in "".join(p.read_text(encoding="utf-8") for p in sorted(service_file.glob("*.py")))
    assert "关联需求" in form_file.read_text(encoding="utf-8")
    assert "requirement_id: form.requirement_id ?? null" in form_file.read_text(encoding="utf-8")
    assert "关联需求" in list_file.read_text(encoding="utf-8")


def test_dashboard_exposes_asset_counts_and_pending_action_counts():
    service_file = ROOT / "services" / "test_workbench_service"
    dashboard_file = ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "pages" / "WorkbenchDashboardPage.vue"

    service = "".join(p.read_text(encoding="utf-8") for p in sorted(service_file.glob("*.py")))
    assert '"system_count"' in service
    assert '"open_bug_count"' in service
    assert '"pending_legacy_count"' in service
    dashboard = dashboard_file.read_text(encoding="utf-8")
    assert "系统数量" in dashboard
    assert "未关闭 Bug 数" in dashboard
    assert "待处理遗留项数" in dashboard


def test_requirement_detail_exposes_requirement_relations_endpoint():
    endpoint_file = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py"
    api_file = ROOT.parent / "frontend" / "src" / "api" / "testWorkbench.js"
    assert 'requirements/{requirement_id}/relations' in endpoint_file.read_text(encoding="utf-8")
    assert "getWorkbenchRequirementRelations" in api_file.read_text(encoding="utf-8")


def test_workbench_projects_do_not_store_or_expose_owner_id():
    model_source = (ROOT / "models" / "models_workbench.py").read_text(encoding="utf-8")
    permission_source = (ROOT / "services" / "test_workbench_service" / "permissions.py").read_text(encoding="utf-8")
    structure_source = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "structure.py").read_text(encoding="utf-8")

    project_model = model_source[model_source.index("class TWProject"):model_source.index("class TWSystem")]
    assert "owner_id" not in project_model
    assert "owner = relationship" not in project_model
    assert "owner_id" not in permission_source
    assert "TWProject.owner_id" not in structure_source


def test_requirement_refinement_does_not_force_a_second_round():
    prompt_file = ROOT / "docs" / "prompt" / "requirement_refinement.md"
    prompt = prompt_file.read_text(encoding="utf-8")
    assert "至少追问两轮" not in prompt
    assert "没有新的高价值疑点" in prompt


def test_refinement_error_action_and_usage_labels_are_compact_tags():
    card_file = ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RefinementMessageCard.vue"
    usage_file = ROOT.parent / "frontend" / "src" / "components" / "AiUsageStatsBar.vue"
    card = card_file.read_text(encoding="utf-8")
    usage = usage_file.read_text(encoding="utf-8")

    assert 'class="error-actions"' in card
    assert 'class="usage-label"' not in usage
    assert 'round>输入' in usage
    assert 'round>输出' in usage
    assert 'round>耗时' in usage


def test_ai_usage_overview_has_independent_model_scope_and_on_demand_metric_help():
    usage_file = ROOT.parent / "frontend" / "src" / "views" / "admin" / "AiUsage.vue"
    usage_api = ROOT / "api" / "v1" / "endpoints" / "ai.py"
    usage_filters = ROOT.parent / "frontend" / "src" / "utils" / "aiUsageFilters.js"
    usage = usage_file.read_text(encoding="utf-8")
    api = usage_api.read_text(encoding="utf-8")
    filters = usage_filters.read_text(encoding="utf-8")

    assert "statsModelScope" in usage
    assert "modelOwnerScope" in usage
    assert "InfoFilled" in usage
    assert "metricHelpVisible" in usage
    assert "全部模型" in usage
    assert "平台模型" in usage
    assert "我的模型" in usage
    assert "不随“我的模型”筛选变化" in usage
    assert "model_owner_scope" in api
    assert "_resolve_usage_user_id" in api
    assert "model_owner_id=current_user.id if model_owner_scope == \"self\" else None" in api
    assert "params.model_owner_scope" in filters


def test_workbench_rules_allocate_requirement_numbers_when_drafts_are_created():
    requirement_file = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py"
    structure_file = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "structure.py"
    service_file = ROOT / "services" / "test_workbench_service"

    requirement = requirement_file.read_text(encoding="utf-8")
    create_start = requirement.index("async def save_requirement")
    create_end = requirement.index('@router.put("/requirements/', create_start)
    assert 'assign_requirement_no(requirement, prefix="REQ")' in requirement[create_start:create_end]

    structure = structure_file.read_text(encoding="utf-8")
    delete_start = structure.index("async def delete_workbench_project")
    delete_end = structure.index('@router.get("/systems")', delete_start)
    assert "await soft_delete_workbench_project_data(db, project, current_user.id, beijing_now())" in structure[delete_start:delete_end]

    service = "".join(p.read_text(encoding="utf-8") for p in sorted(service_file.glob("*.py")))
    cascade_start = service.index("async def soft_delete_workbench_project_data")
    cascade_end = service.index("async def soft_delete_project_business_data", cascade_start)
    for model_name in ("TWSystem", "TWVersion", "TWRequirement", "TWCompletedRequirement", "TWMergedRequirement", "TWTestCase", "TWBugRecord", "TWLegacyItem", "TWTestExecution", "TWBugTransition"):
        assert model_name in service[cascade_start:cascade_end]


def test_ai_merge_accepts_one_typed_source_list_and_creates_merged_asset_only_on_save():
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "merged_ai.py").read_text(encoding="utf-8")
    model = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "models").glob("models_*.py")))

    assert 'source_type: Literal["requirement", "completed_requirement"]' in schema
    assert "source_ids: list[int]" in schema
    pre_save = endpoint[:endpoint.index('@router.post("/requirements/merge-ai/save")')]
    assert '@router.post("/requirements/merge-ai/ask/stream")' in pre_save
    assert '@router.post("/requirements/merge-ai/compose/stream")' in pre_save
    assert "TWMergedRequirement(" not in pre_save
    assert 'assign_requirement_no(merged, prefix="MREQ")' in endpoint
    assert "source_requirement_ids" in model


def test_batch_operations_carry_and_enforce_the_current_workbench_scope():
    schema_file = ROOT / "schemas" / "test_workbench.py"
    requirement_file = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py"
    test_case_file = ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "test_cases.py"
    requirement_page = ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementManagementPage.vue"

    schema = schema_file.read_text(encoding="utf-8")
    assert schema.count("project_id: int | None = None") >= 2
    assert schema.count("system_ids: list[int] = Field(default_factory=list)") >= 2
    assert schema.count("version_ids: list[int] = Field(default_factory=list)") >= 2
    assert "data.project_id" in requirement_file.read_text(encoding="utf-8")
    assert "data.project_id" in test_case_file.read_text(encoding="utf-8")
    assert "batchScopePayload" in requirement_page.read_text(encoding="utf-8")


def test_completed_requirements_are_independent_records_linked_to_original_requirements():
    model = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "models").glob("models_*.py")))
    schema = (ROOT / "schemas" / "test_workbench.py").read_text(encoding="utf-8")

    assert "class TWCompletedRequirement" in model
    assert '__tablename__ = "tw_completed_requirements"' in model
    assert "source_requirement_id" in model
    assert "confirm_status" in model
    assert "class TWCompletedRequirementSave" in schema


def test_ai_completion_save_creates_a_draft_child_without_overwriting_the_original_requirement():
    endpoint = (ROOT / "api" / "v1" / "endpoints" / "test_workbench_routers" / "requirements.py").read_text(encoding="utf-8")
    save_start = endpoint.index("async def save_requirement_ai_result")
    save_body = endpoint[save_start:]

    assert "TWCompletedRequirement(" in save_body
    assert 'confirm_status="draft"' in save_body
    assert "requirement.markdown_content = markdown" not in save_body


def test_requirement_management_exposes_independent_original_completed_and_merged_tabs():
    page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "pages" / "WorkbenchRequirementPage.vue").read_text(encoding="utf-8")
    api = (ROOT.parent / "frontend" / "src" / "api" / "testWorkbench.js").read_text(encoding="utf-8")

    assert "原始需求" in page
    assert "AI补全需求" in page
    assert "AI合并需求" in page
    assert "activeTab" in page
    assert "getWorkbenchCompletedRequirements" in api


def test_requirement_preview_uses_markdown_content_for_ai_completion_and_edits_title():
    preview = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementPreviewDrawer.vue").read_text(encoding="utf-8")

    assert "props.detail?.markdown_content || props.detail?.original_content" in preview
    assert "v-model=\"titleDraft\"" in preview
    assert "saveMarkdown" in preview
    assert "保存需求内容" in preview


def test_ai_merge_requires_model_confirmation_before_first_model_call():
    drawer = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementRefinementDrawer.vue").read_text(encoding="utf-8")
    composable = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "composables" / "useRequirementRefinement.js").read_text(encoding="utf-8")

    # 首轮模型调用前必须停留在确认页；发起后（含失败）不再回退，避免吞掉错误气泡。
    assert "v-if=\"!conversationStarted\"" in drawer
    assert "if (props.bootstrap) await bootstrap()" not in drawer
    start = composable[composable.index("const start = async () =>"):]
    assert "if (!canStart.value) return" in start
    assert "conversationBroken.value = false" in start
    assert "await runStream({ mode: 'start'" in start


def test_completed_requirement_status_uses_compact_primary_and_secondary_display():
    page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementManagementPage.vue").read_text(encoding="utf-8")

    assert 'class="status-cell"' in page
    assert 'class="status-stale"' in page
    assert 'label="状态" min-width="110"' in page


def test_all_requirement_types_use_side_by_side_edit_preview_with_copy_actions():
    preview = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementPreviewDrawer.vue").read_text(encoding="utf-8")
    merged_detail = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "MergedRequirementDetailDrawer.vue").read_text(encoding="utf-8")
    requirement_page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementManagementPage.vue").read_text(encoding="utf-8")
    merged_page = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "pages" / "WorkbenchMergedRequirementPage.vue").read_text(encoding="utf-8")

    assert "updateWorkbenchRequirement" in preview
    assert 'v-if="!editing" @click="startEdit">编辑</el-button>' in preview
    assert 'class="preview-columns"' in preview
    assert "copyEditingContent" in preview
    assert "copyPreviewContent" in preview
    assert "titleDraft" in merged_detail
    assert "copyEditingContent" in merged_detail
    assert "copyPreviewContent" in merged_detail
    assert "titleDraft" in merged_page
    assert "title: detailDrawer.titleDraft" in merged_page
    assert 'prop="title" label="需求标题" min-width="180"' in requirement_page
    assert 'label="操作" width="180" fixed="right"' in requirement_page
    assert "merge-entry-hint" not in merged_page


def test_all_requirement_editors_provide_toc_and_bidirectional_scroll_sync():
    preview = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementPreviewDrawer.vue").read_text(encoding="utf-8")
    merged_detail = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "MergedRequirementDetailDrawer.vue").read_text(encoding="utf-8")

    for editor in (preview, merged_detail):
        assert 'class="md-toc"' in editor
        assert "const onEditorScroll" in editor
        assert "const onPreviewScroll" in editor
        assert "const scrollToHeading" in editor
        assert "requestAnimationFrame(() => { syncing = false })" in editor


def test_requirement_prompts_prohibit_system_numbers_in_generated_body():
    prompt_root = ROOT.parent / "backend" / "docs" / "prompt"
    prompt_names = (
        "requirement_refinement.md",
        "requirement_compose.md",
        "requirement_merge_refinement.md",
        "requirement_merge_compose.md",
        "test_workbench_requirement_merge.md",
    )
    for prompt_name in prompt_names:
        prompt = (prompt_root / prompt_name).read_text(encoding="utf-8")
        assert "不得在生成正文中输出来源需求编号" in prompt


def test_requirement_details_show_source_number_and_hide_version_pointer_column():
    preview = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "RequirementPreviewDrawer.vue").read_text(encoding="utf-8")
    merged_detail = (ROOT.parent / "frontend" / "src" / "views" / "test-workbench" / "components" / "MergedRequirementDetailDrawer.vue").read_text(encoding="utf-8")

    assert "source_requirement_no" in preview
    assert 'prop="req_no"' in merged_detail
    assert 'prop="version_pointer"' not in merged_detail
