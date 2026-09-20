"""统一响应格式和异常处理"""
import json
import logging
import traceback
from copy import deepcopy
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_LOG_BODY_LENGTH = 5000
MAX_LOG_RESPONSE_LENGTH = 5000
MAX_LOG_HEADER_LENGTH = 3000
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "passwd",
    "pwd",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "client_secret",
    "api_key",
    "apikey",
    "key_secret",
    "sign",
    "phone",
    "mobile",
    "telephone",
    "密码",
    "手机号",
    "密钥",
    "令牌",
    "webhook",
    "credential",
    "access_key",
    "private_key",
}
MASKED_VALUE = "******已脱敏******"


class ResponseModel(BaseModel):
    """统一响应模型"""
    code: int = 200
    message: str = "success"
    data: Any = None


def success_response(data: Any = None, message: str = "success") -> dict:
    """成功响应，自动转换ORM对象为dict"""
    return {
        "code": 200,
        "message": message,
        "data": _convert_data(data)
    }


def _convert_data(data: Any) -> Any:
    """递归转换ORM对象和列表为纯dict，避免懒加载"""
    if data is None:
        return None
    if isinstance(data, list):
        return [_convert_data(item) for item in data]
    if hasattr(data, '__table__'):
        return {c.name: getattr(data, c.name) for c in data.__table__.columns if c.name != 'password'}
    if isinstance(data, dict):
        return {k: _convert_data(v) for k, v in data.items()}
    return data


def error_response(code: int = 400, message: str = "error", data: Any = None) -> dict:
    """错误响应"""
    return {
        "code": code,
        "message": message,
        "data": data
    }


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}\n... 已截断，原始长度 {len(value)} 字符"


def _is_sensitive_key(key: Any) -> bool:
    key_text = str(key).lower()
    return any(sensitive in key_text for sensitive in SENSITIVE_KEYS)


def _mask_sensitive_data(data: Any) -> Any:
    if isinstance(data, dict):
        result = {}
        kv_key = data.get("key")
        for key, value in data.items():
            if key == "value" and kv_key is not None and _is_sensitive_key(kv_key):
                result[key] = MASKED_VALUE
            else:
                result[key] = MASKED_VALUE if _is_sensitive_key(key) else _mask_sensitive_data(value)
        return result
    if isinstance(data, list):
        return [_mask_sensitive_data(item) for item in data]
    return data


def mask_sensitive_data(data: Any) -> Any:
    """返回业务展示用的敏感信息脱敏副本。"""
    return _mask_sensitive_data(data)


def mask_sensitive_text(value: Any) -> Any:
    """脱敏 JSON 文本；无法安全解析的文本整体隐藏。"""
    if not isinstance(value, str) or not value:
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return MASKED_VALUE
    return json.dumps(mask_sensitive_data(parsed), ensure_ascii=False)


def restore_masked_data(original: Any, incoming: Any) -> Any:
    """合并表单回传数据时，保留未修改的脱敏字段。"""
    if isinstance(incoming, str) and incoming in {MASKED_VALUE, "***"}:
        return deepcopy(original)
    if isinstance(original, dict) and isinstance(incoming, dict):
        return {
            key: restore_masked_data(original.get(key), value)
            for key, value in incoming.items()
        }
    if isinstance(original, list) and isinstance(incoming, list):
        return [
            restore_masked_data(original[index] if index < len(original) else None, value)
            for index, value in enumerate(incoming)
        ]
    return incoming


def restore_masked_text(original: Any, incoming: Any) -> Any:
    """合并 JSON 文本中的脱敏字段，无法解析时按普通字符串处理。"""
    if isinstance(incoming, str) and incoming in {MASKED_VALUE, "***"}:
        return deepcopy(original)
    if not isinstance(original, str) or not isinstance(incoming, str):
        return incoming
    try:
        original_json = json.loads(original)
        incoming_json = json.loads(incoming)
    except (TypeError, ValueError):
        return incoming
    merged = restore_masked_data(original_json, incoming_json)
    return json.dumps(merged, ensure_ascii=False, separators=(",", ":"))


def _format_json_like(data: Any, limit: int) -> str:
    try:
        text = json.dumps(
            _mask_sensitive_data(jsonable_encoder(data)),
            ensure_ascii=False,
            indent=2,
        )
    except Exception:
        text = str(data)
    return _truncate_text(text, limit)


def _format_headers(headers) -> str:
    safe_headers = {}
    for key, value in headers.items():
        safe_headers[key] = MASKED_VALUE if _is_sensitive_key(key) else value
    return _format_json_like(safe_headers, MAX_LOG_HEADER_LENGTH)


def _mask_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        query_items = [
            (key, MASKED_VALUE if _is_sensitive_key(key) else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))
    except Exception:
        return url


async def _format_request_body(request) -> str:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type:
        return "[multipart/form-data omitted]"
    if "application/octet-stream" in content_type:
        return "[application/octet-stream omitted]"

    try:
        body = await request.body()
    except Exception as exc:
        return "[请求体不可用（异常处理上下文中无法读取）]"

    if not body:
        return "[empty]"

    if "application/json" in content_type:
        try:
            return _format_json_like(json.loads(body.decode("utf-8")), MAX_LOG_BODY_LENGTH)
        except Exception:
            pass

    if "application/x-www-form-urlencoded" in content_type:
        try:
            form_items = dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
            return _format_json_like(form_items, MAX_LOG_BODY_LENGTH)
        except Exception:
            pass

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return f"[binary body omitted, {len(body)} bytes]"

    return _truncate_text(text, MAX_LOG_BODY_LENGTH)


def _client_ip(request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def build_error_log_message(
    request,
    *,
    title: str,
    response_content: dict,
    exception: Exception | None = None,
    include_traceback: bool = False,
) -> str:
    response_code = response_content.get("code")
    response_message = response_content.get("message")
    lines = [
        f"{title} code={response_code} | {request.method} {request.url.path} | {response_message}",
        "",
        "【关键信息】",
        f"请求方法：{request.method}",
        f"请求地址：{_mask_url(str(request.url))}",
        f"响应码：{response_code}",
        f"响应消息：{response_message}",
        f"客户端IP：{_client_ip(request)}",
    ]

    if exception is not None:
        lines.extend([
            f"异常类型：{exception.__class__.__name__}",
            f"异常信息：{exception}",
        ])

    lines.extend([
        "",
        "【请求头】",
        _format_headers(request.headers),
        "",
        "【请求体】",
        await _format_request_body(request),
        "",
        "【响应】",
        _format_json_like(response_content, MAX_LOG_RESPONSE_LENGTH),
    ])

    if include_traceback and exception is not None:
        lines.extend([
            "",
            "【异常堆栈】",
            "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
        ])

    return "\n".join(lines)


class UnifiedException(Exception):
    """自定义统一异常"""
    def __init__(self, code: int = 400, message: str = "error", data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(self.message)


async def unified_exception_handler(request, exc: UnifiedException):
    """统一异常处理器"""
    content = {
        "code": exc.code,
        "message": exc.message,
        "data": exc.data
    }
    logger.error(await build_error_log_message(
        request,
        title="业务异常",
        response_content=content,
        exception=exc,
    ))
    return JSONResponse(
        status_code=200,
        content=content
    )


def _safe_validation_errors(exc: RequestValidationError) -> list[dict]:
    """Convert Pydantic validation errors to JSON-safe dicts (ValueError etc not serializable)."""
    safe = []
    for err in exc.errors():
        item = {"type": err.get("type", ""), "loc": list(err.get("loc", [])), "msg": str(err.get("msg", ""))}
        # ctx.error may contain Exception objects — convert to string
        ctx = err.get("ctx") or {}
        safe_ctx = {}
        for k, v in ctx.items():
            safe_ctx[k] = str(v) if isinstance(v, Exception) else v
        item["ctx"] = safe_ctx
        safe.append(item)
    return safe


async def validation_exception_handler(request, exc: RequestValidationError):
    """请求验证异常处理器"""
    content = {
        "code": 400,
        "message": "请求参数验证失败",
        "data": {"errors": _safe_validation_errors(exc)}
    }
    logger.error(await build_error_log_message(
        request,
        title="参数校验失败",
        response_content=content,
        exception=exc,
    ))
    return JSONResponse(
        status_code=200,
        content=content
    )


async def http_exception_handler(request, exc):
    """HTTP异常处理器 - 统一返回HTTP 200，保留认证和权限业务码"""
    if exc.status_code in (401, 403):
        detail = str(exc.detail or "").strip()
        default_messages = {
            "not authenticated": "未登录或登录状态已失效，请重新登录",
            "forbidden": "权限不足",
        }
        content = {
            "code": 401 if exc.status_code == 401 else 403,
            "message": default_messages.get(detail.lower(), detail or "未授权，请重新登录"),
            "data": None
        }
        logger.error(await build_error_log_message(
            request,
            title="HTTP异常",
            response_content=content,
            exception=exc,
        ))
        return JSONResponse(
            status_code=200,
            content=content,
            headers=exc.headers
        )
    else:
        content = {
            "code": 400,
            "message": exc.detail or "请求失败",
            "data": None
        }
        logger.error(await build_error_log_message(
            request,
            title="HTTP异常",
            response_content=content,
            exception=exc,
        ))
        return JSONResponse(
            status_code=200,
            content=content
        )
