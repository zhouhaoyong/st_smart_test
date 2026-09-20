import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import httpx

from core.response import UnifiedException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import api.v1.endpoints.executor as executor
import api.v1.endpoints.executions as executions_endpoint
from api.v1.endpoints.executor import _format_runtime_step_result
from services.auth_config import AuthResolution
from services.execution_engine import runner


def test_execution_audit_description_distinguishes_interface_and_case_results():
    assert executor._build_execution_audit_description(
        "订单", "interface", "查询订单", "success"
    ) == "订单项目内，接口调试：查询订单，成功"
    assert executor._build_execution_audit_description(
        "订单", "case", "登录校验", "failed"
    ) == "订单项目内，用例运行：登录校验，失败"


def test_execution_audit_status_follows_final_report_status():
    assert executions_endpoint._execution_audit_status(SimpleNamespace(status="success")) == "success"
    assert executions_endpoint._execution_audit_status(SimpleNamespace(status="failed")) == "failed"
    assert executions_endpoint._execution_audit_status(None) == "failed"


def test_parallel_case_exception_produces_one_case_failure_detail():
    details, test_case_id, case_passed, case_failed = runner._build_case_failure_result(
        report_id=9,
        case_order=3,
        test_case_id=21,
        error_message="连接池不可用",
    )

    assert len(details) == 1
    assert details[0]["report_id"] == 9
    assert details[0]["step_order"] == 3
    assert details[0]["test_case_id"] == 21
    assert details[0]["status"] == "failed"
    assert details[0]["error_message"] == "连接池不可用"
    assert details[0]["diff_result"] == []
    assert test_case_id == 21
    assert case_passed == 0
    assert case_failed == 1


def test_format_runtime_step_result_preserves_the_run_case_response_shape():
    result = _format_runtime_step_result(
        {
            "status": "success",
            "request_data": {
                "method": "GET",
                "url": "https://api.example.test/orders/7",
                "headers": {"X-Trace": "trace-1"},
                "params": {"verbose": True},
                "path_params": [{"key": "id", "value": 7}],
                "body": None,
                "proxy": None,
                "service": {"key": "orders", "name": "订单服务"},
            },
            "response_data": {
                "status_code": 200,
                "headers": {"content-type": "application/json"},
                "text": '{"code":200}',
                "json": {"code": 200},
            },
            "duration": 18,
            "logs": "--- 断言结果 ---",
            "diff_result": [],
        },
        "查询订单",
    )

    assert result == {
        "name": "查询订单",
        "status": "success",
        "msg": "HTTP 200 (18ms) — 断言全部通过",
        "statusCode": 200,
        "duration": 18,
        "request": {
            "method": "GET",
            "url": "https://api.example.test/orders/7",
            "headers": {"X-Trace": "trace-1"},
            "params": {"verbose": True},
            "path_params": [{"key": "id", "value": 7}],
            "body": None,
            "proxy": None,
            "service": {"key": "orders", "name": "订单服务"},
        },
        "response": {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "body": {"code": 200},
            "text": '{"code":200}',
        },
        "assertion_results": {"passed": 0, "failed": 0, "diffs": []},
        "logs": "--- 断言结果 ---",
    }


def test_format_runtime_step_result_uses_execution_error_when_request_fails():
    result = _format_runtime_step_result(
        {
            "status": "failed",
            "request_data": {},
            "response_data": {},
            "duration": 4,
            "error_message": "请求超时",
            "diff_result": [],
            "logs": "请求超时",
        },
        "查询订单",
    )

    assert result["status"] == "error"
    assert result["statusCode"] == 0
    assert result["msg"] == "请求超时"


@pytest.mark.asyncio
async def test_run_case_delegates_step_execution_to_the_shared_execution_engine(monkeypatch):
    environment = SimpleNamespace(
        id=1,
        project_id=5,
        base_url="https://api.example.test",
        port=None,
        global_variables={},
    )
    project = SimpleNamespace(id=5)
    interface = SimpleNamespace(
        id=11,
        name="查询订单",
        collection=SimpleNamespace(is_deleted=False, project_id=5),
    )

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Database:
        def __init__(self):
            self.values = iter([environment, project, interface])

        async def execute(self, statement):
            return Result(next(self.values))

    runtime_result = {
        "status": "success",
        "request_data": {"method": "GET", "url": "https://api.example.test/orders"},
        "response_data": {"status_code": 200, "headers": {}, "text": "{}", "json": {}},
        "duration": 3,
        "logs": "",
        "diff_result": [],
    }
    execute_step = AsyncMock(return_value=runtime_result)
    monkeypatch.setattr(executor, "execute_step", execute_step)
    monkeypatch.setattr(executor, "log_user_operation", AsyncMock())

    result = await executor.run_test_case(
        data=executor.RunCaseRequest(environment_id=1, interface_id=11),
        current_user=SimpleNamespace(id=1, is_superuser=True, is_manager=True),
        db=Database(),
    )

    assert result["code"] == 200
    assert result["data"]["total_passed"] == 1
    execute_step.assert_awaited_once()


@pytest.mark.asyncio
async def test_debug_delegates_step_execution_to_the_shared_execution_engine(monkeypatch):
    environment = SimpleNamespace(
        id=1,
        project_id=5,
        base_url="https://api.example.test",
        port=None,
        timeout=30,
        global_variables={},
        global_headers={},
        service_config={},
        token_config={},
        proxy_config={},
        proxy_http=None,
        proxy_https=None,
    )
    project = SimpleNamespace(id=5)
    interface = SimpleNamespace(
        id=11,
        name="查询订单",
        collection_id=3,
        service_key="orders",
        path_params=[],
        pre_script="",
        post_script="",
    )

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def scalars(self):
            return self

        def all(self):
            return []

    class Database:
        def __init__(self):
            self.values = iter([environment, project, interface, project])

        async def execute(self, statement):
            return Result(next(self.values))

    runtime_result = {
        "status": "success",
        "request_data": {"method": "GET", "url": "https://api.example.test/orders"},
        "response_data": {"status_code": 200, "headers": {}, "text": "{}", "json": {}},
        "duration": 3,
        "logs": "",
        "diff_result": [],
        "assertion_results": {"passed": 0, "failed": 0, "diffs": []},
    }
    execute_step = AsyncMock(return_value=runtime_result)
    monkeypatch.setattr(executor, "execute_step", execute_step)
    monkeypatch.setattr(executor, "log_user_operation", AsyncMock())

    result = await executor.debug_request(
        data=executor.DebugRequest(
            environment_id=1,
            interface_id=11,
            method="GET",
            url="/orders",
            base_url="https://api.example.test",
        ),
        current_user=SimpleNamespace(id=1, is_superuser=True, is_manager=True),
        db=Database(),
    )

    assert result["code"] == 200
    assert result["data"]["success"] is True
    execute_step.assert_awaited_once()


@pytest.mark.asyncio
async def test_shared_step_execution_exposes_assertion_summary(monkeypatch):
    interface = SimpleNamespace(
        method="GET",
        url="/health",
        headers=[],
        query_params=[],
        path_params=[],
        body_type="",
        body_content="",
        pre_script="",
        post_script="",
    )
    environment = SimpleNamespace(
        id=1,
        base_url="https://api.example.test",
        port=None,
        timeout=30,
        global_headers={},
        service_config={},
        token_config={},
        proxy_config={},
        proxy_http=None,
        proxy_https=None,
    )
    monkeypatch.setattr(
        runner,
        "build_request_kwargs",
        AsyncMock(return_value={
            "method": "GET",
            "url": "https://api.example.test/health",
            "headers": {},
            "params": {},
            "path_params": [],
            "json": None,
            "data": None,
            "files": None,
            "timeout": 30,
            "service": None,
            "auth_service": None,
            "auth_resolution": AuthResolution(headers={}),
        }),
    )
    monkeypatch.setattr(
        runner,
        "execute_with_auth_retry",
        AsyncMock(return_value=(
            httpx.Response(200, json={"code": 200}),
            AuthResolution(headers={}),
        )),
    )

    result = await runner.execute_step(
        interface=interface,
        environment=environment,
        case_or_step=SimpleNamespace(
            param_overrides={},
            assertions=[{
                "type": "status_code",
                "expression": "status_code",
                "operator": "eq",
                "expected": 200,
            }],
            script=None,
        ),
        global_vars={},
        step_order=1,
    )

    assert result["assertion_results"]["passed"] == 1
    assert result["assertion_results"]["failed"] == 0
    assert result["assertion_results"]["diffs"][0]["result"] == "pass"


@pytest.mark.asyncio
async def test_shared_step_execution_without_assertions_accepts_any_2xx_status(monkeypatch):
    interface = SimpleNamespace(
        method="POST",
        url="/orders",
        headers=[],
        query_params=[],
        path_params=[],
        body_type="",
        body_content="",
        pre_script="",
        post_script="",
    )
    environment = SimpleNamespace(
        id=1,
        base_url="https://api.example.test",
        port=None,
        timeout=30,
        global_headers={},
        service_config={},
        token_config={},
        proxy_config={},
        proxy_http=None,
        proxy_https=None,
    )
    monkeypatch.setattr(
        runner,
        "build_request_kwargs",
        AsyncMock(return_value={
            "method": "POST",
            "url": "https://api.example.test/orders",
            "headers": {},
            "params": {},
            "path_params": [],
            "json": None,
            "data": None,
            "files": None,
            "timeout": 30,
            "service": None,
            "auth_service": None,
            "auth_resolution": AuthResolution(headers={}),
        }),
    )
    monkeypatch.setattr(
        runner,
        "execute_with_auth_retry",
        AsyncMock(return_value=(
            httpx.Response(201, json={"id": 1}),
            AuthResolution(headers={}),
        )),
    )

    result = await runner.execute_step(
        interface=interface,
        environment=environment,
        case_or_step=SimpleNamespace(param_overrides={}, assertions=[], script=None),
        global_vars={},
        step_order=1,
    )

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_shared_step_execution_without_assertions_rejects_non_2xx_status(monkeypatch):
    interface = SimpleNamespace(
        method="GET",
        url="/orders",
        headers=[],
        query_params=[],
        path_params=[],
        body_type="",
        body_content="",
        pre_script="",
        post_script="",
    )
    environment = SimpleNamespace(
        id=1,
        base_url="https://api.example.test",
        port=None,
        timeout=30,
        global_headers={},
        service_config={},
        token_config={},
        proxy_config={},
        proxy_http=None,
        proxy_https=None,
    )
    monkeypatch.setattr(
        runner,
        "build_request_kwargs",
        AsyncMock(return_value={
            "method": "GET",
            "url": "https://api.example.test/orders",
            "headers": {},
            "params": {},
            "path_params": [],
            "json": None,
            "data": None,
            "files": None,
            "timeout": 30,
            "service": None,
            "auth_service": None,
            "auth_resolution": AuthResolution(headers={}),
        }),
    )
    monkeypatch.setattr(
        runner,
        "execute_with_auth_retry",
        AsyncMock(return_value=(
            httpx.Response(500, json={"message": "error"}),
            AuthResolution(headers={}),
        )),
    )

    result = await runner.execute_step(
        interface=interface,
        environment=environment,
        case_or_step=SimpleNamespace(param_overrides={}, assertions=[], script=None),
        global_vars={},
        step_order=1,
    )

    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_shared_step_execution_empty_script_overrides_do_not_run_interface_scripts(monkeypatch):
    interface = SimpleNamespace(
        method="GET",
        url="/health",
        headers=[],
        query_params=[],
        path_params=[],
        body_type="",
        body_content="",
        pre_script="interface-pre",
        post_script="interface-post",
    )
    environment = SimpleNamespace(
        id=1,
        base_url="https://api.example.test",
        port=None,
        timeout=30,
        global_headers={},
        service_config={},
        token_config={},
        proxy_config={},
        proxy_http=None,
        proxy_https=None,
    )
    monkeypatch.setattr(
        runner,
        "build_request_kwargs",
        AsyncMock(return_value={
            "method": "GET",
            "url": "https://api.example.test/health",
            "headers": {},
            "params": {},
            "path_params": [],
            "json": None,
            "data": None,
            "files": None,
            "timeout": 30,
            "service": None,
            "auth_service": None,
            "auth_resolution": AuthResolution(headers={}),
        }),
    )
    monkeypatch.setattr(
        runner,
        "execute_with_auth_retry",
        AsyncMock(return_value=(
            httpx.Response(200, json={"ok": True}),
            AuthResolution(headers={}),
        )),
    )
    executed_scripts = []

    def record_script(_context, script):
        executed_scripts.append(script)
        return ""

    monkeypatch.setattr(runner.ScriptContext, "execute", record_script)

    await runner.execute_step(
        interface=interface,
        environment=environment,
        case_or_step=SimpleNamespace(
            param_overrides={"pre_script": "", "post_script": ""},
            assertions=[],
            script=None,
        ),
        global_vars={},
        step_order=1,
    )

    assert executed_scripts == []


@pytest.mark.asyncio
async def test_build_execution_global_vars_without_parameter_set_keeps_empty_environment_empty():
    class UnexpectedDatabaseCall:
        async def execute(self, _statement):
            raise AssertionError("未选择参数集时不应查询参数集")

    environment = SimpleNamespace(global_variables={})
    result = await runner.build_execution_global_vars(
        UnexpectedDatabaseCall(),
        environment,
        parameter_set_id=None,
    )

    assert result == {}
    assert result is not environment.global_variables


@pytest.mark.asyncio
async def test_debug_mode_can_keep_business_errors_as_api_errors(monkeypatch):
    monkeypatch.setattr(
        runner,
        "build_request_kwargs",
        AsyncMock(side_effect=UnifiedException(code=400, message="临时文件不存在或已过期")),
    )

    with pytest.raises(UnifiedException, match="临时文件不存在"):
        await runner.execute_step(
            interface=SimpleNamespace(),
            environment=SimpleNamespace(),
            case_or_step=SimpleNamespace(param_overrides={}, assertions=[], script=None),
            global_vars={},
            step_order=1,
            propagate_business_errors=True,
        )
