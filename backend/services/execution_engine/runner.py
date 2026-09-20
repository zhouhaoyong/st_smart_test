"""Execution main flow: running execution sets and individual steps."""
import json
import time
import ssl
from copy import deepcopy
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal
from models.models import (
    ExecutionSet, ExecutionItem, TestCase, Interface,
    Environment, Report, ReportDetail, ParameterSet, ParameterItem,
)
from services.http_headers import encode_headers_for_httpx
from services.auth_config import execute_with_auth_retry
from services.proxy_config import select_proxy_for_url
from core.timezone import beijing_now
from core.response import UnifiedException

from ._shared import logger, REPORT_DETAIL_COLUMNS
from .variables import (
    DotDict,
    ScriptContext,
    resolve_variables,
    resolve_dict,
    resolve_typed_dict,
    extract_jsonpath,
)
from .assertions import run_assertions
from .request_builder import _fetch_auth_token_for_execution, build_request_kwargs


async def build_execution_global_vars(
    db: AsyncSession,
    environment: Environment,
    parameter_set_id: int | None = None,
) -> dict:
    """Build execution variables consistently for debug, case, and set execution."""
    source_variables = environment.global_variables
    global_vars = deepcopy(source_variables) if isinstance(source_variables, dict) else {}
    if not parameter_set_id:
        return global_vars

    parameter_set_result = await db.execute(
        select(ParameterSet).where(
            ParameterSet.id == parameter_set_id,
            ParameterSet.project_id == environment.project_id,
            ParameterSet.is_deleted == False,
        )
    )
    if not parameter_set_result.scalar_one_or_none():
        raise UnifiedException(code=400, message="参数集不属于当前项目")

    item_result = await db.execute(
        select(ParameterItem).where(
            ParameterItem.parameter_set_id == parameter_set_id,
            ParameterItem.is_deleted == False,
        )
    )
    parameter_types = global_vars.get("__parameter_types")
    parameter_types = deepcopy(parameter_types) if isinstance(parameter_types, dict) else {}
    for item in item_result.scalars().all():
        global_vars[item.key] = item.value
        parameter_types[item.key] = item.type or "string"
    if parameter_types:
        global_vars["__parameter_types"] = parameter_types
    return global_vars


def _build_case_failure_result(
    report_id: int,
    case_order: int,
    test_case_id: int,
    error_message: str,
) -> tuple[list[dict], int, int, int]:
    """Return one failed report detail for a case-level execution exception."""
    return ([{
        "report_id": report_id,
        "step_order": case_order,
        "test_case_id": test_case_id,
        "status": "failed",
        "request_data": {},
        "response_data": {},
        "expected_response": {},
        "actual_response": {},
        "diff_result": [],
        "logs": error_message,
        "duration": 0,
        "retry_attempts": 0,
        "error_message": error_message,
    }], test_case_id, 0, 1)


def _override_or_default(overrides: dict, key: str, default):
    if isinstance(overrides, dict) and key in overrides and overrides[key] is not None:
        return overrides[key]
    return default


def _request_body_value(request_kwargs: dict):
    return (
        request_kwargs.get("json")
        if request_kwargs.get("json") is not None
        else request_kwargs.get("data")
    )


def _sync_script_request_mutations(
    request_context: dict,
    request_kwargs: dict,
    request_data: dict,
) -> None:
    """把脚本对请求方法、地址、请求头、参数和请求体的修改同步回真实请求。"""
    if not isinstance(request_context, dict):
        return

    if "method" in request_context and request_context["method"]:
        request_kwargs["method"] = str(request_context["method"]).upper()
    if "url" in request_context and request_context["url"] is not None:
        request_kwargs["url"] = str(request_context["url"])
    for field in ("headers", "params", "path_params"):
        if field in request_context and isinstance(request_context[field], (dict, list)):
            request_kwargs[field] = request_context[field]

    if "body" in request_context:
        body = request_context["body"]
        request_kwargs["json"] = None
        request_kwargs["data"] = None
        if body is not None:
            if request_kwargs.get("body_type") == "json":
                request_kwargs["json"] = body
            else:
                request_kwargs["data"] = body

    request_data.update({
        "method": request_kwargs.get("method", "GET"),
        "url": request_kwargs.get("url", ""),
        "headers": request_kwargs.get("headers", {}),
        "params": request_kwargs.get("params", {}),
        "path_params": request_kwargs.get("path_params", []),
        "body": _request_body_value(request_kwargs),
    })


async def execute_execution_set(
    execution_set_id: int,
    db: AsyncSession,
    report_id: int | None = None,
) -> int:
    """
    Execute all test cases in an execution set.
    Creates a Report and returns the report ID.
    """
    # Load execution set
    result = await db.execute(
        select(ExecutionSet).where(ExecutionSet.id == execution_set_id, ExecutionSet.is_deleted == False)
    )
    exec_set = result.scalar_one_or_none()
    if not exec_set:
        raise ValueError("执行集不存在")

    # Load environment
    result = await db.execute(
        select(Environment).where(Environment.id == exec_set.environment_id, Environment.is_deleted == False)
    )
    environment = result.scalar_one_or_none()
    if not environment:
        raise ValueError("运行环境不存在")

    # Load execution items (exclude soft-deleted)
    result = await db.execute(
        select(ExecutionItem)
        .join(TestCase, ExecutionItem.test_case_id == TestCase.id)
        .join(Interface, TestCase.interface_id == Interface.id)
        .where(
            ExecutionItem.execution_set_id == execution_set_id,
            ExecutionItem.is_deleted == False,
            TestCase.is_deleted == False,
            Interface.is_deleted == False,
        )
        .order_by(ExecutionItem.order)
    )
    items = result.scalars().all()

    logger.info(f"执行集 {exec_set.name}(id={execution_set_id}): 加载到 {len(items)} 个执行项, 执行模式={exec_set.execution_mode}")

    if not items:
        raise ValueError("执行集中没有关联的用例")

    if report_id is not None:
        result = await db.execute(
            select(Report).where(Report.id == report_id, Report.is_deleted == False)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise ValueError("执行报告不存在")
        report.status = "running"
        report.start_time = beijing_now()
        report.end_time = None
        report.duration = None
        report.total_steps = 0
        report.passed_steps = 0
        report.failed_steps = 0
        report.total_cases = 0
        report.passed_cases = 0
        report.failed_cases = 0
        report.pass_rate = 0.0
        report.execution_mode = exec_set.execution_mode or "serial"
    else:
        report = Report(
            name=f"{exec_set.name}-{beijing_now().strftime('%Y%m%d_%H%M%S')}",
            project_id=exec_set.project_id,
            execution_set_id=exec_set.id,
            status="running",
            execution_mode=exec_set.execution_mode or "serial",
            start_time=beijing_now(),
            total_steps=0,
            passed_steps=0,
            failed_steps=0,
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            pass_rate=0.0,
        )
        db.add(report)
    await db.flush()

    # Extract global variables from environment and the explicitly selected parameter set.
    global_vars = await build_execution_global_vars(db, environment, exec_set.parameter_set_id)

    execution_auth_context = {"tokens": {}}

    total_passed = 0
    total_failed = 0
    total_cases = 0
    passed_cases = 0
    failed_cases = 0
    step_order = 0
    start_time = time.time()

    is_parallel = exec_set.execution_mode == "parallel"

    async def execute_one_case(item, case_order, local_global_vars, db_session, http_client, auth_context):
        """执行单个用例，返回 (结果列表, test_case_id, case_passed, case_failed)"""
        results = []
        case_passed = 0
        case_failed = 0

        tc_result = await db_session.execute(
            select(TestCase).where(TestCase.id == item.test_case_id, TestCase.is_deleted == False)
        )
        test_case = tc_result.scalar_one_or_none()
        if not test_case:
            logger.warning(f"用例 item.test_case_id={item.test_case_id} 不存在或已删除")
            results.append({
                "report_id": report.id,
                "step_order": case_order,
                "test_case_id": item.test_case_id,
                "status": "failed",
                "request_data": {},
                "response_data": {},
                "error_message": "关联的用例不存在",
                "duration": 0,
            })
            return results, item.test_case_id, 0, 1

        iface_result = await db_session.execute(
            select(Interface).where(Interface.id == test_case.interface_id, Interface.is_deleted == False)
        )
        interface = iface_result.scalar_one_or_none()
        if not interface:
            results.append({
                "report_id": report.id,
                "step_order": case_order,
                "test_case_id": test_case.id,
                "status": "failed",
                "request_data": {},
                "response_data": {},
                "error_message": "关联的接口不存在",
                "duration": 0,
            })
            return results, test_case.id, 0, 1

        retry_count = max(0, min(3, exec_set.retry_count or 0))
        last_result = None
        final_attempt = 0
        for attempt in range(retry_count + 1):
            final_attempt = attempt
            last_result = await execute_step(
                interface, environment, test_case, local_global_vars, case_order, client=http_client, auth_context=auth_context
            )
            # Propagate script variables to global vars for subsequent steps
            step_vars = last_result.get("script_variables", {})
            if isinstance(step_vars, dict):
                local_global_vars.update(step_vars)
            if last_result["status"] == "success":
                break

        results.append({
            "report_id": report.id,
            "step_order": case_order,
            "test_case_id": test_case.id,
            "status": last_result["status"],
            "request_data": last_result["request_data"],
            "response_data": last_result["response_data"],
            "expected_response": last_result.get("expected_response"),
            "actual_response": last_result.get("actual_response"),
            "diff_result": last_result.get("diff_result"),
            "logs": last_result.get("logs", ""),
            "duration": last_result.get("duration", 0),
            "retry_attempts": final_attempt,
            "error_message": last_result.get("error_message"),
        })
        if last_result["status"] == "success":
            case_passed += 1
        else:
            case_failed += 1

        return results, test_case.id, case_passed, case_failed

    try:
        if is_parallel:
            # 并行执行：信号量限制并发数，避免连接池耗尽导致接口挂起
            import asyncio
            max_parallel = max(1, min(5, len(items)))
            semaphore = asyncio.Semaphore(max_parallel)

            async def _run_one_case(item, pre_order, local_vars):
                async with semaphore:
                    try:
                        async with AsyncSessionLocal() as case_db:
                            _ssl_ctx = ssl.create_default_context()
                            _ssl_ctx.check_hostname = False
                            _ssl_ctx.verify_mode = ssl.CERT_NONE
                            async with httpx.AsyncClient(
                                verify=_ssl_ctx,
                            ) as case_client:
                                return await execute_one_case(item, pre_order, local_vars, case_db, case_client, execution_auth_context)
                    except Exception as e:
                        # 单个用例异常也要计入总用例数，返回失败结果
                        logger.exception(f"用例 {item.test_case_id} 执行异常: {e}")
                        return _build_case_failure_result(
                            report_id=report.id,
                            case_order=pre_order,
                            test_case_id=item.test_case_id,
                            error_message=str(e) or "用例执行异常",
                        )

            # 预计算每用例的步序号偏移
            tasks = []
            order_offset = 0
            for idx, item in enumerate(items):
                order_offset += 1
                pre_order = order_offset
                local_vars = dict(global_vars)
                tasks.append(_run_one_case(item, pre_order, local_vars))

            all_case_results = await asyncio.gather(*tasks)

            # 结果写回：主会话统一写入 ReportDetail 和更新 TestCase
            for step_results, test_case_id, case_passed, case_failed in all_case_results:
                if test_case_id is None:
                    continue

                # 从主会话重新查询 TestCase（并行任务用的是独立会话，对象已分离）
                tc_result = await db.execute(
                    select(TestCase).where(TestCase.id == test_case_id)
                )
                attached_tc = tc_result.scalar_one_or_none()

                for sr in step_results:
                    detail = ReportDetail(**{k: v for k, v in sr.items() if k in REPORT_DETAIL_COLUMNS})
                    db.add(detail)
                    if sr["status"] == "success":
                        total_passed += 1
                    else:
                        total_failed += 1

                total_cases += 1
                if attached_tc:
                    attached_tc.last_run_at = beijing_now()
                    attached_tc.last_run_status = "failed" if case_failed > 0 else "success"
                if case_failed == 0:
                    passed_cases += 1
                else:
                    failed_cases += 1
        else:
            # 串行执行：复用同一个 HTTP 客户端和 DB 会话
            _ssl_ctx = ssl.create_default_context()
            _ssl_ctx.check_hostname = False
            _ssl_ctx.verify_mode = ssl.CERT_NONE
            async with httpx.AsyncClient(
                verify=_ssl_ctx,
            ) as shared_client:
                for item in items:
                    step_order += 1
                    step_results, test_case_id, case_passed, case_failed = await execute_one_case(
                        item, step_order, global_vars, db, shared_client, execution_auth_context
                    )
                    if test_case_id is None:
                        continue

                    for sr in step_results:
                        detail = ReportDetail(**{k: v for k, v in sr.items() if k in REPORT_DETAIL_COLUMNS})
                        db.add(detail)
                        if sr["status"] == "success":
                            total_passed += 1
                        else:
                            total_failed += 1

                    # 串行模式下用例从主会话加载，可直接更新
                    tc_result = await db.execute(
                        select(TestCase).where(TestCase.id == test_case_id)
                    )
                    attached_tc = tc_result.scalar_one_or_none()
                    total_cases += 1
                    if attached_tc:
                        attached_tc.last_run_at = beijing_now()
                        attached_tc.last_run_status = "failed" if case_failed > 0 else "success"
                    if case_failed == 0:
                        passed_cases += 1
                    else:
                        failed_cases += 1

        # Update report
        total_steps = total_passed + total_failed
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"执行完成: total_cases={total_cases}, passed={passed_cases}, failed={failed_cases}, steps={total_steps}")
        report.total_steps = total_steps
        report.passed_steps = total_passed
        report.failed_steps = total_failed
        report.total_cases = total_cases
        report.passed_cases = passed_cases
        report.failed_cases = failed_cases
        report.pass_rate = (passed_cases / total_cases * 100) if total_cases > 0 else 0
        report.duration = duration_ms
        report.end_time = beijing_now()
        report.status = "success" if failed_cases == 0 else "failed"

        await db.commit()

    except Exception as e:
        logger.exception("Error during execution")
        report.status = "failed"
        report.end_time = beijing_now()
        report.duration = int((time.time() - start_time) * 1000)
        report.total_steps = total_passed + total_failed
        report.passed_steps = total_passed
        report.failed_steps = total_failed
        report.total_cases = total_cases
        report.passed_cases = passed_cases
        report.failed_cases = failed_cases
        report.pass_rate = (passed_cases / total_cases * 100) if total_cases > 0 else 0
        await db.commit()

    return report.id




async def execute_step(
    interface: Interface,
    environment: Environment,
    case_or_step,
    global_vars: dict,
    step_order: int,
    client: httpx.AsyncClient | None = None,
    auth_context: dict | None = None,
    external_param_overrides: dict | None = None,
    token_fetcher=None,
    explicit_auth_header: bool | None = None,
    propagate_business_errors: bool = False,
) -> dict:
    """Execute a single test case request and return the result dict"""
    step_start = time.time()
    logs = []
    request_data = {}
    response_data = {}
    result = {
        "status": "failed",
        "request_data": {},
        "response_data": {},
        "logs": "",
        "duration": 0,
        "error_message": None,
        "diff_result": None,
        "expected_response": None,
        "actual_response": None,
    }

    try:
        # Build script context
        ctx = ScriptContext()
        ctx._variables = dict(global_vars)

        # Build request kwargs
        request_kwargs = await build_request_kwargs(
            interface,
            environment,
            case_or_step,
            ctx._variables,
            auth_context,
            token_fetcher=token_fetcher,
            explicit_auth_header=explicit_auth_header,
        )
        request_proxy = select_proxy_for_url(
            request_kwargs.get("url"),
            environment.proxy_config,
            environment.proxy_http,
            environment.proxy_https,
        )
        kwargs_files = request_kwargs.get("files")
        request_data = {
            "method": request_kwargs["method"],
            "url": request_kwargs["url"],
            "headers": request_kwargs.get("headers", {}),
            "params": request_kwargs.get("params", {}),
            "path_params": resolve_typed_dict(request_kwargs.get("path_params", []), ctx._variables),
            "body": _request_body_value(request_kwargs),
            "proxy": request_proxy,
            "service": request_kwargs.get("service"),
        }
        if kwargs_files:
            request_data["files"] = {k: v[0] for k, v in kwargs_files.items()}
        result["request_data"] = request_data

        # Execute pre-script: external override > case override > interface default
        param_overrides = external_param_overrides if external_param_overrides is not None else (getattr(case_or_step, "param_overrides", None) or {})
        is_dict_override = isinstance(param_overrides, dict)
        effective_pre_script = _override_or_default(
            param_overrides,
            "pre_script",
            interface.pre_script,
        ) if is_dict_override else interface.pre_script
        if effective_pre_script:
            ctx.request = DotDict(request_data)
            pre_logs = ctx.execute(effective_pre_script)
            if pre_logs:
                logs.append("--- 前置脚本日志 ---")
                logs.append(pre_logs)

            _sync_script_request_mutations(ctx.request, request_kwargs, request_data)

        # Execute case-level script (pre-request)
        case_script = getattr(case_or_step, "script", None)
        if case_script:
            case_ctx = ScriptContext()
            case_ctx._variables = ctx._variables
            case_ctx.request = DotDict(request_data)
            case_logs = case_ctx.execute(case_script)
            if case_logs:
                logs.append("--- 用例脚本日志 ---")
                logs.append(case_logs)
            ctx._variables.update(case_ctx._variables)
            _sync_script_request_mutations(case_ctx.request, request_kwargs, request_data)

        # Re-resolve after scripts may have set variables
        request_kwargs["method"] = str(request_kwargs.get("method") or "GET").upper()
        request_kwargs["url"] = resolve_variables(request_kwargs["url"], ctx._variables)
        request_kwargs["headers"] = resolve_dict(request_kwargs.get("headers", {}), ctx._variables)
        if request_kwargs.get("json") is not None:
            request_kwargs["json"] = resolve_typed_dict(request_kwargs["json"], ctx._variables)
        if request_kwargs.get("params") is not None:
            request_kwargs["params"] = resolve_typed_dict(request_kwargs["params"], ctx._variables)
        request_kwargs["path_params"] = resolve_typed_dict(request_kwargs.get("path_params", []), ctx._variables)
        request_proxy = select_proxy_for_url(
            request_kwargs.get("url"),
            environment.proxy_config,
            environment.proxy_http,
            environment.proxy_https,
        )
        request_data.update({
            "url": request_kwargs["url"],
            "headers": request_kwargs.get("headers", {}),
            "params": request_kwargs.get("params", {}),
            "path_params": resolve_typed_dict(request_kwargs.get("path_params", []), ctx._variables),
            "method": request_kwargs["method"],
            "body": _request_body_value(request_kwargs),
            "proxy": request_proxy,
        })
        result["request_data"] = request_data

        # Send HTTP request (reuse client if provided, otherwise create one)
        _ssl_ctx = ssl.create_default_context()
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = ssl.CERT_NONE

        async def _do_request(cli: httpx.AsyncClient, request_headers: dict):
            kwargs_files = request_kwargs.get("files")
            if kwargs_files:
                # multipart/form-data: use data + files, no json
                return await cli.request(
                    method=request_kwargs["method"],
                    url=request_kwargs["url"],
                    headers=encode_headers_for_httpx(request_headers),
                    params=request_kwargs.get("params"),
                    data=request_kwargs.get("data"),
                    files=kwargs_files,
                    timeout=request_kwargs.get("timeout", 30),
                )
            return await cli.request(
                method=request_kwargs["method"],
                url=request_kwargs["url"],
                headers=encode_headers_for_httpx(request_headers),
                params=request_kwargs.get("params"),
                json=request_kwargs.get("json"),
                data=request_kwargs.get("data"),
                timeout=request_kwargs.get("timeout", 30),
            )

        async def _send_request(request_headers):
            if client is not None and not request_proxy:
                return await _do_request(client, request_headers)
            async with httpx.AsyncClient(
                proxy=request_proxy,
                verify=_ssl_ctx,
            ) as temp_client:
                return await _do_request(temp_client, request_headers)

        http_response, refreshed_auth = await execute_with_auth_retry(
            headers=request_kwargs.get("headers", {}),
            auth_config=environment.token_config,
            service=request_kwargs.get("auth_service"),
            token_fetcher=token_fetcher or _fetch_auth_token_for_execution,
            request_func=_send_request,
            execution_context=auth_context,
            auth_cache_scope=getattr(environment, "id", None),
            initial_resolution=request_kwargs.get("auth_resolution"),
        )
        request_kwargs["headers"] = refreshed_auth.headers
        request_data["headers"] = refreshed_auth.headers
        result["request_data"] = request_data

        # Build response data
        resp_text = http_response.text
        resp_json = None
        try:
            resp_json = http_response.json()
        except Exception:
            resp_json = None

        response_data = {
            "status_code": http_response.status_code,
            "headers": dict(http_response.headers),
            "text": resp_text,
            "json": resp_json,
        }
        result["response_data"] = response_data

        # Execute post-script: case override > interface default
        effective_post_script = _override_or_default(
            param_overrides,
            "post_script",
            interface.post_script,
        ) if is_dict_override else interface.post_script
        if effective_post_script:
            ctx.response = response_data
            post_logs = ctx.execute(effective_post_script)
            if post_logs:
                logs.append("--- 后置脚本日志 ---")
                logs.append(post_logs)

        # Propagate script variables so subsequent steps can reference them via {{var}}
        # Filter out internal keys (prefixed with __) and non-serializable objects
        propagated_vars = {
            k: v for k, v in ctx._variables.items()
            if not k.startswith("__") and not callable(v)
        }
        result["script_variables"] = propagated_vars

        # Run assertions
        assertions = getattr(case_or_step, "assertions", None) or []
        step_duration = int((time.time() - step_start) * 1000)

        # Always build per-assertion actual values for report transparency
        actual_response = {}
        for a in assertions:
            if a.get("enabled", True) is False:
                continue
            a_type = a.get("type", "jsonpath")
            expression = a.get("expression", "")
            if a_type == "jsonpath":
                val = extract_jsonpath(resp_json or {}, expression)
            elif a_type == "status_code":
                val = response_data.get("status_code", 0)
            elif a_type == "response_time":
                val = step_duration
            elif a_type == "contains":
                val = json.dumps(resp_json if resp_json is not None else response_data.get("text", ""), ensure_ascii=False)
            else:
                val = None
            actual_response[str(expression)] = str(val) if val is not None else ""

        enabled_assertions = [a for a in assertions if a.get("enabled", True) is not False]
        if enabled_assertions:
            passed, failed, diffs = run_assertions(enabled_assertions, response_data, step_duration, logs)
            logs.append(f"--- 断言结果: {passed}通过, {failed}失败 ---")

            # Always include all assertion results (pass + fail) for report
            result["assertion_results"] = {
                "passed": passed,
                "failed": failed,
                "diffs": diffs,
            }
            result["diff_result"] = diffs
            result["expected_response"] = {
                a.get("expression", ""): a.get("expected", "")
                for a in enabled_assertions
            }
            result["actual_response"] = actual_response

            if failed > 0:
                result["status"] = "failed"
                result["error_message"] = f"断言失败: {failed}个"
            else:
                result["status"] = "success"
        else:
            result["assertion_results"] = {"passed": 0, "failed": 0, "diffs": []}
            result["expected_response"] = {}
            result["actual_response"] = actual_response
            status_code = response_data.get("status_code", 0)
            if isinstance(status_code, int) and 200 <= status_code < 300:
                result["status"] = "success"
            else:
                result["status"] = "failed"
                result["error_message"] = f"HTTP 状态码 {status_code}"

        result["duration"] = step_duration
        result["logs"] = "\n".join(logs)

    except UnifiedException as exc:
        if propagate_business_errors:
            raise
        result["duration"] = int((time.time() - step_start) * 1000)
        result["error_message"] = str(exc)
        logs.append(f"[Error] {exc}")
        result["logs"] = "\n".join(logs)

    except httpx.TimeoutException:
        result["duration"] = int((time.time() - step_start) * 1000)
        result["error_message"] = "请求超时"
        logs.append("[Error] 请求超时")
        result["logs"] = "\n".join(logs)

    except httpx.ConnectError as e:
        result["duration"] = int((time.time() - step_start) * 1000)
        result["error_message"] = f"连接失败: {e}"
        logs.append(f"[Error] 连接失败: {e}")
        result["logs"] = "\n".join(logs)

    except Exception as e:
        result["duration"] = int((time.time() - step_start) * 1000)
        result["error_message"] = f"执行异常: {e}"
        logs.append(f"[Error] 执行异常: {e}")
        result["logs"] = "\n".join(logs)

    return result
