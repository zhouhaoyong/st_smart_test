from types import SimpleNamespace

from services.api_test_workflow import (
    INTERFACE_STATUS_DONE,
    INTERFACE_STATUS_PENDING,
    PENDING_REASON_CHANGED,
    PENDING_REASON_NEW,
    PENDING_REASON_LEGACY,
    TEST_CASE_CONFIRM_PENDING,
    TEST_CASE_CONFIRM_CONFIRMED,
    TEST_CASE_CONFIRM_REASON_INTERFACE_CHANGED,
    mark_interface_done,
    mark_interface_pending,
    mark_test_case_pending,
    apply_import_workflow_state,
)
from init_db import _PENDING_ADD_COLUMNS, _PENDING_BACKFILL_STATEMENTS
from services.file_import_dedup import merge_case_overrides


def test_mark_interface_pending_keeps_reason_until_user_marks_done():
    interface = SimpleNamespace(workflow_status=INTERFACE_STATUS_DONE, pending_reason=None)

    mark_interface_pending(interface, PENDING_REASON_CHANGED)

    assert interface.workflow_status == INTERFACE_STATUS_PENDING
    assert interface.pending_reason == PENDING_REASON_CHANGED

    mark_interface_done(interface)

    assert interface.workflow_status == INTERFACE_STATUS_DONE
    assert interface.pending_reason is None


def test_mark_interface_pending_accepts_new_and_legacy_reasons():
    interface = SimpleNamespace(workflow_status=None, pending_reason=None)

    mark_interface_pending(interface, PENDING_REASON_NEW)
    assert interface.workflow_status == INTERFACE_STATUS_PENDING
    assert interface.pending_reason == PENDING_REASON_NEW

    mark_interface_pending(interface, PENDING_REASON_LEGACY)
    assert interface.pending_reason == PENDING_REASON_LEGACY


def test_mark_test_case_pending_for_interface_change():
    test_case = SimpleNamespace(confirm_status=TEST_CASE_CONFIRM_CONFIRMED, confirm_reason=None)

    mark_test_case_pending(test_case, TEST_CASE_CONFIRM_REASON_INTERFACE_CHANGED)

    assert test_case.confirm_status == TEST_CASE_CONFIRM_PENDING
    assert test_case.confirm_reason == TEST_CASE_CONFIRM_REASON_INTERFACE_CHANGED


def test_name_only_import_change_does_not_reset_workflow_states():
    interface = SimpleNamespace(workflow_status=INTERFACE_STATUS_DONE, pending_reason=None)
    test_case = SimpleNamespace(confirm_status=TEST_CASE_CONFIRM_CONFIRMED, confirm_reason=None)

    apply_import_workflow_state(interface, change_reasons=["name"], linked_cases=[test_case])

    assert interface.workflow_status == INTERFACE_STATUS_DONE
    assert interface.pending_reason is None
    assert test_case.confirm_status == TEST_CASE_CONFIRM_CONFIRMED
    assert test_case.confirm_reason is None


def test_definition_import_change_resets_interface_and_linked_cases():
    interface = SimpleNamespace(workflow_status=INTERFACE_STATUS_DONE, pending_reason=None)
    test_case = SimpleNamespace(confirm_status=TEST_CASE_CONFIRM_CONFIRMED, confirm_reason=None)

    apply_import_workflow_state(interface, change_reasons=["url"], linked_cases=[test_case])

    assert interface.workflow_status == INTERFACE_STATUS_PENDING
    assert interface.pending_reason == PENDING_REASON_CHANGED
    assert test_case.confirm_status == TEST_CASE_CONFIRM_PENDING
    assert test_case.confirm_reason == TEST_CASE_CONFIRM_REASON_INTERFACE_CHANGED


def test_completed_api_test_status_migration_leaves_empty_startup_slots():
    """已完成的一次性迁移不应在每次启动时重复执行，但保留后续迁移入口。"""
    assert _PENDING_ADD_COLUMNS == {}
    assert _PENDING_BACKFILL_STATEMENTS == ()


def test_merge_case_overrides_syncs_removed_and_added_request_fields():
    current = {
        "method": "GET",
        "url": "/old",
        "query_params": [
            {"key": "keep", "value": "user-value"},
            {"key": "removed", "value": "should-disappear"},
        ],
        "path_params": [],
        "body_type": "json",
        "body_content": {"keep": "user-value", "removed": "should-disappear"},
        "assertions": [{"expression": "$.code"}],
        "pre_script": "user script",
    }
    incoming_add = {
        "method": "POST",
        "url": "/new",
        "query_params": [
            {"key": "keep", "value": "document-value"},
            {"key": "added", "value": "document-value"},
        ],
        "path_params": [],
        "body_type": "json",
        "body_content": {"keep": "document-value", "added": "document-value"},
        "body_schema_types": {"keep": "string", "added": "string"},
    }
    incoming_remove = {
        **incoming_add,
        "query_params": [{"key": "keep", "value": "document-value"}],
        "body_content": {"keep": "document-value"},
        "body_schema_types": {"keep": "string"},
    }

    merged = merge_case_overrides(current, incoming_add)

    assert merged["method"] == "POST"
    assert merged["url"] == "/new"
    # 同时出现增删可能是参数改名，保持原结构；分别导入时才自动同步。
    assert [item["key"] for item in merged["query_params"]] == ["keep", "removed"]
    assert merged["query_params"][0]["value"] == "user-value"
    merged_add = merge_case_overrides(
        {**current, "query_params": [{"key": "keep", "value": "user-value"}], "body_content": {"keep": "user-value"}},
        incoming_add,
    )
    assert [item["key"] for item in merged_add["query_params"]] == ["keep", "added"]
    assert merged_add["query_params"][1]["value"] == ""
    merged_remove = merge_case_overrides(current, incoming_remove)
    assert [item["key"] for item in merged_remove["query_params"]] == ["keep"]
    assert merged_add["body_content"] == {"keep": "user-value", "added": ""}
    assert merged_remove["body_content"] == {"keep": "user-value"}
    assert merged["assertions"] == current["assertions"]
    assert merged["pre_script"] == "user script"
