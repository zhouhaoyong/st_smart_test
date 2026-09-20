import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_empty_run_request_has_no_executable_item_but_interface_request_does():
    from api.v1.endpoints.executor import RunCaseRequest, _resolve_run_items

    assert _resolve_run_items(RunCaseRequest(environment_id=1)) == []
    assert len(_resolve_run_items(RunCaseRequest(environment_id=1, interface_id=9))) == 1


@pytest.mark.asyncio
async def test_case_json_override_applies_to_an_empty_json_object():
    from services.execution_engine.request_builder import build_request_kwargs

    interface = SimpleNamespace(
        method="POST",
        url="/orders",
        service_key=None,
        headers=[],
        query_params=[],
        path_params=[],
        body_type="json",
        body_content="{}",
    )
    environment = SimpleNamespace(
        id=1,
        base_url="https://api.example.test",
        port=None,
        service_config={},
        global_headers={},
        token_config={},
        timeout=30,
    )
    case = SimpleNamespace(param_overrides={"json": {"new": "value"}})

    result = await build_request_kwargs(interface, environment, case, {})

    assert result["json"] == {"new": "value"}


def test_environment_delete_reference_message_lists_execution_sets():
    from api.v1.endpoints.environments import _build_environment_reference_error

    assert _build_environment_reference_error([
        SimpleNamespace(name="回归执行集"),
        SimpleNamespace(name="冒烟执行集"),
    ]) == "执行集「回归执行集、冒烟执行集」已引用当前环境，无法删除"


def test_default_environment_api_is_removed_but_legacy_database_column_remains():
    from api.v1.endpoints.environments import EnvironmentCreate
    from models.models import Environment

    assert "is_default" not in EnvironmentCreate.model_fields
    assert "is_default" in Environment.__table__.columns


def test_execution_mode_accepts_only_supported_values():
    from api.v1.endpoints.executions import ExecutionSetCreate

    with pytest.raises(ValidationError):
        ExecutionSetCreate(
            name="回归",
            project_id=1,
            environment_id=2,
            execution_mode="invalid",
        )


def test_case_tree_node_keeps_confirmation_state():
    from api.v1.endpoints.testcases import _case_tree_node

    node = _case_tree_node({
        "id": 3,
        "name": "订单成功",
        "priority": "high",
        "owner": "测试",
        "last_run_status": "success",
        "path_params": [],
        "confirm_status": "pending",
        "confirm_status_label": "待确认",
        "confirm_reason": "manual",
        "confirm_reason_label": "人工创建",
    })

    assert node["confirm_status"] == "pending"
    assert node["confirm_status_label"] == "待确认"
    assert node["confirm_reason_label"] == "人工创建"


def test_confirm_pending_test_cases_only_updates_pending_cases_and_clears_reason():
    from services.api_test_workflow import (
        TEST_CASE_CONFIRM_CONFIRMED,
        TEST_CASE_CONFIRM_PENDING,
        confirm_pending_test_cases,
    )

    pending = SimpleNamespace(
        id=1,
        confirm_status=TEST_CASE_CONFIRM_PENDING,
        confirm_reason="interface_changed",
        updated_by=None,
    )
    confirmed = SimpleNamespace(
        id=2,
        confirm_status=TEST_CASE_CONFIRM_CONFIRMED,
        confirm_reason=None,
        updated_by=3,
    )

    result = confirm_pending_test_cases([pending, confirmed], user_id=9)

    assert result == [pending]
    assert pending.confirm_status == TEST_CASE_CONFIRM_CONFIRMED
    assert pending.confirm_reason is None
    assert pending.updated_by == 9
    assert confirmed.confirm_status == TEST_CASE_CONFIRM_CONFIRMED
    assert confirmed.updated_by == 3


@pytest.mark.asyncio
async def test_batch_confirm_test_cases_is_scoped_to_interface_and_audited(monkeypatch):
    from api.v1.endpoints import testcases as endpoint

    class Result:
        def __init__(self, *, scalar=None, rows=None):
            self.scalar = scalar
            self.rows = rows or []

        def scalar_one_or_none(self):
            return self.scalar

        def scalars(self):
            return self

        def all(self):
            return self.rows

    interface = SimpleNamespace(id=7, collection_id=8, name="注册用户")
    project = SimpleNamespace(id=9, name="订单项目")
    pending = SimpleNamespace(
        id=1,
        confirm_status="pending",
        confirm_reason="interface_changed",
        updated_by=None,
    )
    already_confirmed = SimpleNamespace(
        id=2,
        confirm_status="confirmed",
        confirm_reason=None,
        updated_by=3,
    )
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[
            Result(scalar=interface),
            Result(scalar=project),
            Result(rows=[pending, already_confirmed]),
        ]),
        commit=AsyncMock(),
    )
    current_user = SimpleNamespace(id=9, real_name="测试用户")
    audit = AsyncMock()
    monkeypatch.setattr(endpoint, "ensure_project_asset_manage", lambda *_args: None)
    monkeypatch.setattr(endpoint, "log_user_operation", audit)

    response = await endpoint.batch_confirm_test_cases(
        endpoint.BatchConfirmRequest(interface_id=7),
        current_user,
        db,
    )

    assert response["data"] == {"confirmed": 1}
    assert response["message"] == "已确认 1 条用例"
    assert pending.confirm_status == "confirmed"
    assert pending.confirm_reason is None
    assert pending.updated_by == 9
    assert already_confirmed.updated_by == 3
    db.commit.assert_awaited_once()
    audit.assert_awaited_once()
    assert audit.await_args.kwargs["target_id"] == 7
    assert audit.await_args.kwargs["details"] == {"interface_id": 7, "confirmed_count": 1}


def test_interface_tree_node_keeps_workflow_status():
    from api.v1.endpoints.testcases import _interface_tree_node

    node = _interface_tree_node({
        "interface_id": 7,
        "interface_name": "健康检查",
        "interface_method": "GET",
        "interface_url": "/health",
        "workflow_status": "done",
        "cases": [],
    })

    assert node["workflow_status"] == "done"
    assert node["workflow_status_label"] == "已处理"
    assert node["name"] == "健康检查"
    assert node["children"] == []


def test_service_identifier_is_part_of_interface_deduplication():
    from services.file_import_dedup import service_keys_match

    assert service_keys_match("order", "order")
    assert not service_keys_match("order", "payment")
    assert service_keys_match(None, "")
    assert not service_keys_match(None, "order")


def test_script_request_mutations_sync_all_request_parts():
    from services.execution_engine.runner import _sync_script_request_mutations

    request_context = {
        "method": "POST",
        "url": "/orders/{{id}}",
        "headers": {"X-Trace": "trace-2"},
        "params": {"verbose": True},
        "path_params": [{"key": "id", "value": "7"}],
        "body": {"id": 7},
    }
    request_kwargs = {
        "method": "GET",
        "url": "/old",
        "headers": {},
        "params": {},
        "path_params": [],
        "body_type": "json",
        "json": None,
        "data": None,
    }
    request_data = {}

    _sync_script_request_mutations(request_context, request_kwargs, request_data)

    assert request_kwargs["method"] == "POST"
    assert request_kwargs["url"] == "/orders/{{id}}"
    assert request_kwargs["headers"] == {"X-Trace": "trace-2"}
    assert request_kwargs["params"] == {"verbose": True}
    assert request_kwargs["path_params"] == [{"key": "id", "value": "7"}]
    assert request_kwargs["json"] == {"id": 7}
    assert request_data["body"] == {"id": 7}


def test_batch_move_summary_reports_partial_success_without_hiding_failures():
    from api.v1.endpoints.interfaces import _summarize_batch_move_results

    summary = _summarize_batch_move_results(
        [1, 3],
        [{"interface_id": 2, "message": "接口不存在"}],
    )

    assert summary == {
        "success_ids": [1, 3],
        "failed": [{"interface_id": 2, "message": "接口不存在"}],
        "success_count": 2,
        "failed_count": 1,
    }


def test_report_send_time_is_formatted_in_beijing_time_and_detail_diff_accepts_list():
    from api.v1.endpoints.reports import ReportDetailResponse, _format_report_datetime

    assert _format_report_datetime(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)) == "2026-01-01 20:00:00"
    ReportDetailResponse(
        id=1,
        report_id=2,
        step_order=1,
        status="failed",
        diff_result=[],
    )
