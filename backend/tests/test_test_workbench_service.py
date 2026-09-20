import pytest
from types import SimpleNamespace

from core.response import UnifiedException
from services.test_workbench_service import (
    assert_same_workbench_scope,
    can_manage_project_workbench_record,
    can_manage_workbench_project_settings,
    can_operate_bug_workflow,
    execution_result_details,
    get_active_workbench_record,
    ensure_scoped_unique_value,
    get_workbench_readonly_metadata,
)
from models.models import TWRequirement
from services.test_workbench_audit import soft_delete_workbench_records
from services.ai_model_service import build_ai_model_preview


class Scope:
    def __init__(self, id=3, project_id=1, system_id=2, version_id=3):
        self.id = id
        self.project_id = project_id
        self.system_id = system_id
        self.version_id = version_id


class WorkbenchUser:
    def __init__(self, user_id, *, is_manager=False, is_superuser=False):
        self.id = user_id
        self.is_manager = is_manager
        self.is_superuser = is_superuser
        self.real_name = "测试用户"


class WorkbenchProject:
    def __init__(self, created_by=1):
        self.created_by = created_by


class WorkbenchRecord:
    def __init__(self, created_by=2, assignee_id=None, verifier_id=None):
        self.created_by = created_by
        self.assignee_id = assignee_id
        self.verifier_id = verifier_id


def test_project_creator_manager_and_record_creator_can_manage_workbench_record():
    project = WorkbenchProject(created_by=1)
    record = WorkbenchRecord(created_by=2)

    assert can_manage_project_workbench_record(WorkbenchUser(1), project, record)
    assert can_manage_project_workbench_record(WorkbenchUser(2), project, record)
    assert can_manage_project_workbench_record(WorkbenchUser(3, is_manager=True), project, record)
    assert can_manage_project_workbench_record(WorkbenchUser(4, is_superuser=True), project, record)
    assert not can_manage_project_workbench_record(WorkbenchUser(5), project, record)


def test_only_workbench_project_creator_and_super_admin_can_delete_project():
    project = WorkbenchProject(created_by=1)

    assert can_manage_workbench_project_settings(WorkbenchUser(1), project)
    assert can_manage_workbench_project_settings(WorkbenchUser(4, is_superuser=True), project)
    assert not can_manage_workbench_project_settings(WorkbenchUser(3, is_manager=True), project)
    assert not can_manage_workbench_project_settings(WorkbenchUser(5), project)


def test_bug_assignee_and_verifier_can_only_perform_their_own_workflow_action():
    project = WorkbenchProject(created_by=1)
    bug = WorkbenchRecord(created_by=2, assignee_id=3, verifier_id=4)

    assert can_operate_bug_workflow(WorkbenchUser(3), project, bug, "resolve")
    assert not can_operate_bug_workflow(WorkbenchUser(3), project, bug, "verify")
    assert can_operate_bug_workflow(WorkbenchUser(4), project, bug, "verify")
    assert can_operate_bug_workflow(WorkbenchUser(1), project, bug, "verify")
    assert can_operate_bug_workflow(WorkbenchUser(5, is_manager=True), project, bug, "resolve")


def test_scope_check_allows_related_assets_in_same_version():
    assert_same_workbench_scope(Scope(), Scope(), "测试用例")


def test_scope_check_allows_asset_in_current_version_entity():
    version = Scope(id=3)
    del version.version_id

    assert_same_workbench_scope(version, Scope(version_id=3), "测试用例")


def test_scope_check_rejects_asset_from_another_version():
    with pytest.raises(UnifiedException, match="不属于当前版本"):
        assert_same_workbench_scope(Scope(), Scope(version_id=4), "测试用例")


def test_execution_details_rejects_removed_execution_results():
    with pytest.raises(UnifiedException, match="执行结果"):
        execution_result_details("not_tested")

    with pytest.raises(UnifiedException, match="执行结果"):
        execution_result_details("blocked")


def test_execution_details_accepts_current_execution_results():
    assert execution_result_details("passed") is None
    assert execution_result_details("failed") is None
    assert execution_result_details("not_executed") is None


def test_execution_details_reject_unknown_result():
    with pytest.raises(UnifiedException, match="执行结果"):
        execution_result_details("unknown")


@pytest.mark.asyncio
async def test_active_workbench_record_loader_filters_soft_deleted_rows():
    record = object()
    statements = []

    class Result:
        def scalar_one_or_none(self):
            return record

    class Database:
        async def execute(self, statement):
            statements.append(statement)
            return Result()

    loaded = await get_active_workbench_record(
        Database(),
        TWRequirement,
        7,
        not_found_message="需求不存在",
    )

    assert loaded is record
    assert "is_deleted" in str(statements[0])


@pytest.mark.asyncio
async def test_scoped_unique_value_checks_only_active_records_in_the_requested_scope():
    statements = []

    class Result:
        def scalar_one_or_none(self):
            return None

    class Database:
        async def execute(self, statement):
            statements.append(statement)
            return Result()

    await ensure_scoped_unique_value(
        Database(),
        TWRequirement,
        scope_field="project_id",
        scope_id=3,
        field_name="title",
        value="  订单需求  ",
        label="需求",
    )

    statement = str(statements[0])
    assert "project_id" in statement
    assert "is_deleted" in statement


@pytest.mark.asyncio
async def test_workbench_readonly_metadata_has_stable_empty_values():
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Database:
        def __init__(self):
            self.results = iter([
                SimpleNamespace(name="订单系统"),
                SimpleNamespace(version_no="v1.2"),
                None,
            ])

        async def execute(self, statement):
            return Result(next(self.results))

    from types import SimpleNamespace

    metadata = await get_workbench_readonly_metadata(
        Database(),
        SimpleNamespace(system_id=2, version_id=3, created_by=0),
    )

    assert metadata == {
        "system_name": "订单系统",
        "version_no": "v1.2",
        "creator_name": "",
    }


def test_soft_delete_workbench_records_applies_the_same_delete_fields_to_each_record():
    from datetime import datetime
    from types import SimpleNamespace

    records = [
        SimpleNamespace(is_deleted=False, deleted_at=None, updated_by=None),
        SimpleNamespace(is_deleted=False, deleted_at=None),
    ]
    deleted_at = datetime(2026, 9, 2, 12, 0, 0)

    soft_delete_workbench_records(records, user_id=9, deleted_at=deleted_at)

    assert all(record.is_deleted for record in records)
    assert all(record.deleted_at == deleted_at for record in records)
    assert records[0].updated_by == 9


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "description", "expected"),
    [
        ("创建", None, "创建项目：审计项目"),
        ("编辑", None, "编辑项目：审计项目"),
        ("删除", None, "删除项目：审计项目"),
        ("复制", "复制项目「来源项目」为「审计项目」", "复制项目「来源项目」为「审计项目」"),
    ],
)
async def test_workbench_project_audit_does_not_add_project_internal_prefix(
    monkeypatch, operation, description, expected,
):
    captured = {}

    async def fake_log_operation(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "api.v1.endpoints.test_workbench_routers._shared.log_operation",
        fake_log_operation,
    )
    from api.v1.endpoints.test_workbench_routers._shared import _audit_workbench_mutation
    from models.models import TWProject

    project = TWProject(id=9, name="审计项目", is_deleted=False)
    await _audit_workbench_mutation(
        db=object(),
        current_user=SimpleNamespace(id=3, real_name="测试用户"),
        operation=operation,
        asset_name="项目",
        record=project,
        description=description,
    )

    assert captured["description"] == expected


def test_ai_model_preview_keeps_common_status_fields_and_feature_prompts():
    model = SimpleNamespace(
        id=3,
        name="测试模型",
        model="model-a",
        connectivity_status="passed",
        reasoning_status="supported",
    )

    result = build_ai_model_preview(
        model,
        {"prompt_preview": "提示词", "generation_prompt_preview": "生成提示词"},
    )

    assert result == {
        "id": 3,
        "name": "测试模型",
        "model": "model-a",
        "connectivity_status": "passed",
        "reasoning_status": "supported",
        "supports_reasoning": True,
        "prompt_preview": "提示词",
        "generation_prompt_preview": "生成提示词",
    }
