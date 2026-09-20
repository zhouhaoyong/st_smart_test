"""
Request executor — 所有接口请求统一通过此模块发出，避免浏览器跨域。
单用例：调试、运行
多用例：执行集批量运行
"""
import json
import ssl
import time
import logging
import httpx
from services.http_headers import encode_headers_for_httpx
from services.execution_engine.assertions import _compare, run_assertions as evaluate_assertions
from services.execution_engine.request_builder import _MIME_TYPES, _guess_mime
from services.execution_engine.variables import extract_jsonpath

logger = logging.getLogger(__name__)


def compare_values(actual, operator: str, expected) -> bool:
    """兼容旧调用方，实际比较统一委托给执行引擎。"""
    normalized_operator = (operator or "eq").strip()
    if normalized_operator == "not_contains":
        return not _compare(actual, "contains", expected)
    if normalized_operator in ("==", "ne", "!="):
        normalized_operator = "eq" if normalized_operator == "==" else "neq"
    return _compare(actual, normalized_operator, expected)


async def execute_single_request(
    method: str,
    url: str,
    headers: dict = None,
    body: str = None,
    params: dict = None,
    timeout: int = 30,
    proxy: str = None,
    service: dict = None,
    files: dict = None,
    path_params: list = None,
) -> dict:
    """发送单次HTTP请求，返回完整的请求/响应数据"""
    headers = headers or {}
    params = params or {}
    start = time.time()

    # 过滤空值：移除空 key、空字符串 value 和 None value
    headers = {k: v for k, v in headers.items() if k and k.strip() and v is not None and v != ''}
    params = {k: v for k, v in params.items() if k and k.strip() and v is not None}

    # 过滤空 body（空字符串或仅空白字符视为无 body）
    if body is not None and (not isinstance(body, str) or not body.strip()):
        body = None

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    request_data = {
        "method": method.upper(),
        "url": url,
        "headers": headers,
        "params": params,
        "path_params": path_params or [],
        "body": body,
        "proxy": proxy or None,
        "service": service,
    }
    if files:
        request_data["files"] = {k: v[0] for k, v in files.items()}

    try:
        async with httpx.AsyncClient(proxy=proxy or None, verify=ssl_ctx, timeout=timeout) as client:
            req_kwargs = dict(
                method=method.upper(),
                url=url,
                headers=encode_headers_for_httpx(headers),
                params=params or None,
                timeout=timeout,
            )

            if files:
                # multipart/form-data: data for form fields, files for file uploads
                if body and isinstance(body, str) and body.strip():
                    try:
                        parsed = json.loads(body)
                        if isinstance(parsed, dict):
                            req_kwargs["data"] = {k: str(v) for k, v in parsed.items() if not str(v).startswith('@')}
                    except (json.JSONDecodeError, TypeError):
                        pass
                req_kwargs["files"] = files
                request_data["body"] = {k: f"@<file:{v[0]}>" for k, v in files.items()}
            else:
                # 处理 body（过滤空值、null 字符串、空白字符）
                json_body = None
                content_body = None
                if body and isinstance(body, str):
                    body = body.strip()
                    if not body or body.lower() in ('null', 'none', 'undefined'):
                        body = None
                if body:
                    try:
                        parsed = json.loads(body) if isinstance(body, str) else body
                        if parsed is not None:
                            json_body = parsed
                    except (json.JSONDecodeError, TypeError):
                        content_body = body if isinstance(body, str) else str(body)

                if method.upper() in ("POST", "PUT", "PATCH"):
                    if json_body is not None:
                        req_kwargs["json"] = json_body
                        request_data["body"] = json_body
                    elif content_body is not None:
                        req_kwargs["content"] = content_body
                        request_data["body"] = content_body

            resp = await client.request(**req_kwargs)

        duration_ms = int((time.time() - start) * 1000)
        resp_text = resp.text
        resp_json = None
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = None

        return {
            "success": True,
            "request": request_data,
            "response": {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp_json if resp_json is not None else resp_text,
                "text": resp_text[:10000],  # 截断过长文本
            },
            "duration": duration_ms,
        }
    except httpx.TimeoutException:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "success": False,
            "request": request_data,
            "response": None,
            "duration": duration_ms,
            "error": "请求超时",
        }
    except httpx.ConnectError as e:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "success": False,
            "request": request_data,
            "response": None,
            "duration": duration_ms,
            "error": f"连接失败: {str(e)}",
        }
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "success": False,
            "request": request_data,
            "response": None,
            "duration": duration_ms,
            "error": f"请求失败: {str(e)}",
        }


# ---------- 单用例执行 ----------

async def execute_single_case(
    method: str,
    url: str,
    headers: dict = None,
    body: str = None,
    params: dict = None,
    timeout: int = 30,
    proxy: str = None,
    assertions: list = None,
    service: dict = None,
    files: dict = None,
    path_params: list = None,
) -> dict:
    """执行单个用例：发请求 + 跑断言，返回完整结果"""
    result = await execute_single_request(method, url, headers, body, params, timeout, proxy, service, files, path_params)
    assertions = assertions or []

    if not result["success"]:
        result["assertion_results"] = None
        result["status"] = "error"
        result["status_code"] = 0
        return result

    resp = result["response"]
    status_code = resp["status_code"]
    duration = result["duration"]

    if assertions:
        response_data = {
            "json": resp.get("body") if isinstance(resp.get("body"), (dict, list)) else None,
            "text": resp.get("text", ""),
            "status_code": resp.get("status_code", 0),
        }
        passed, failed, diffs = evaluate_assertions(assertions, response_data, duration, [])
        case_status = "success" if failed == 0 else "failed"
        fail_msg = f"断言失败: {failed}个" if failed > 0 else ""
    else:
        passed, failed, diffs = 0, 0, []
        case_status = "success"
        fail_msg = ""

    return {
        **result,
        "status": case_status,
        "status_code": status_code,
        "assertion_results": {
            "passed": passed,
            "failed": failed,
            "diffs": diffs,
        },
        "fail_msg": fail_msg,
    }
