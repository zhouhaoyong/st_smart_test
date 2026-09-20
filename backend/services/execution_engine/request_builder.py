"""Request assembly: auth token fetching, file uploads, and HTTP request kwargs."""
import re
import json
import os
import mimetypes

from models.models import Interface, Environment
from services.auth_config import resolve_auth_headers, has_any_auth_header
from services.proxy_config import select_proxy_for_url
from services.service_config import resolve_service_url, service_meta
from services.auth_token import fetch_auth_token
from core.response import UnifiedException
from core.config import settings

from .variables import (
    resolve_variables,
    resolve_dict,
    resolve_typed_value,
    resolve_typed_dict,
    resolve_json_with_typed_variables,
    substitute_path_params,
)


def _override_or_default(overrides: dict, key: str, default):
    if isinstance(overrides, dict) and key in overrides and overrides[key] is not None:
        return overrides[key]
    return default


async def _fetch_auth_token_for_execution(auth: dict, auth_key: str | None = None) -> str | None:
    return await fetch_auth_token(auth, auth_key)


# ====== File Upload (multipart/form-data) Support ======

_MIME_TYPES = {
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.pdf': 'application/pdf',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.svg': 'image/svg+xml',
    '.csv': 'text/csv',
    '.txt': 'text/plain',
    '.zip': 'application/zip',
    '.gz': 'application/gzip',
    '.json': 'application/json',
    '.xml': 'application/xml',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}


def _translate_windows_path(filepath: str) -> str:
    """Translate Windows drive-letter paths (D:\\...) to Docker volume mounts (/mnt/d/...).
    Returns the first path that exists, or the translated path if original doesn't exist."""
    if os.path.exists(filepath):
        return filepath
    # Windows drive letter: D:\xxx → /mnt/d/xxx (prefix configurable via FILE_MOUNT_ROOT)
    m = re.match(r'^([a-zA-Z]):[\\/](.*)$', filepath)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).replace('\\', '/')
        mount_root = settings.FILE_MOUNT_ROOT.rstrip('/')
        translated = f'{mount_root}/{drive}/{rest}'
        if os.path.exists(translated):
            return translated
        return translated
    return filepath


def _guess_mime(path: str) -> str:
    """Guess MIME type from file extension, fallback to octet-stream."""
    ext = os.path.splitext(path)[1].lower()
    return _MIME_TYPES.get(ext) or mimetypes.guess_type(path)[0] or 'application/octet-stream'


def _build_form_data_files(body_content: str | None) -> tuple[dict | None, dict | None]:
    """Parse form-data body JSON into (data, files) for httpx multipart upload.

    Convention:
      - @base64:<mime>;<base64data> → embedded file content (works in all environments)
      - @temp:<stored-name> → server-managed temporary upload reference
      - @/path/to/file → container-local file path
      - @D:\\file.xlsx → auto-translated to /mnt/d/... for Docker mounts
    Returns (data_dict, files_dict) where files_dict values are
    (filename, file_bytes, mime_type) tuples for httpx.
    """
    if not body_content or not body_content.strip():
        return None, None
    try:
        fields = json.loads(body_content)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(fields, dict):
        return None, None

    data = {}
    files = {}
    for key, value in fields.items():
        str_value = str(value) if value is not None else ''
        if str_value.startswith('@'):
            stripped = str_value[1:]  # strip @ prefix

            # @base64:<mime>;<base64data> — embedded file content
            if stripped.startswith('base64:'):
                _, payload = stripped.split(':', 1)
                parts = payload.split(';', 1)
                if len(parts) != 2:
                    raise UnifiedException(code=400, message=f"base64 格式错误，应为 @base64:<mime>;<data>, 字段: {key}")
                mime, b64data = parts
                try:
                    file_bytes = __import__('base64').b64decode(b64data)
                except Exception:
                    raise UnifiedException(code=400, message=f"base64 解码失败，字段: {key}")
                ext = mimetypes.guess_extension(mime) or '.bin'
                filename = f"{key}{ext}"
                files[key] = (filename, file_bytes, mime)
            elif stripped.startswith('oss:'):
                # OSS object reference: @oss:uploads/temp/abc.xlsx
                object_key = stripped[4:]
                from utils.oss_client import _get_oss_client as _get_oss
                oss = _get_oss()
                if not oss:
                    raise UnifiedException(code=400, message=f"OSS 未启用，无法读取: {object_key}")
                try:
                    result = oss.get_object(object_key)
                    file_bytes = result.read()
                except Exception as e:
                    raise UnifiedException(code=400, message=f"OSS 读取失败: {object_key}, 原因: {str(e)}")
                filename = os.path.basename(object_key)
                mime = _guess_mime(filename)
                files[key] = (filename, file_bytes, mime)
            elif stripped.startswith('temp:'):
                # 临时上传只接受服务端生成的文件名，不把真实磁盘路径返回给浏览器。
                stored_name = stripped[5:]
                safe_name = os.path.basename(stored_name)
                if not stored_name or safe_name != stored_name:
                    raise UnifiedException(code=400, message=f"临时文件引用不合法，字段: {key}")
                temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'temp'))
                filepath = os.path.join(temp_dir, safe_name)
                if not os.path.isfile(filepath):
                    raise UnifiedException(code=400, message="临时文件不存在或已过期")
                try:
                    file_bytes = open(filepath, 'rb').read()
                except PermissionError:
                    raise UnifiedException(code=400, message="临时文件无法读取")
                except Exception as e:
                    raise UnifiedException(code=400, message=f"临时文件读取失败: {str(e)}")
                filename = safe_name
                mime = _guess_mime(filepath)
                files[key] = (filename, file_bytes, mime)
            else:
                # File path on disk
                filepath = _translate_windows_path(stripped)
                if not os.path.exists(filepath):
                    raise UnifiedException(code=400, message=f"文件不存在: {filepath}")
                if not os.path.isfile(filepath):
                    raise UnifiedException(code=400, message=f"路径不是文件: {filepath}")
                try:
                    file_bytes = open(filepath, 'rb').read()
                except PermissionError:
                    raise UnifiedException(code=400, message=f"无法读取文件（权限不足）: {filepath}")
                except Exception as e:
                    raise UnifiedException(code=400, message=f"读取文件失败: {filepath}, 原因: {str(e)}")
                filename = os.path.basename(filepath)
                mime = _guess_mime(filepath)
                files[key] = (filename, file_bytes, mime)
        else:
            data[key] = str_value
    return (data if data else None, files if files else None)


async def build_request_kwargs(
    interface: Interface,
    environment: Environment,
    case_or_step,
    variables: dict,
    auth_context: dict | None = None,
    token_fetcher=None,
    explicit_auth_header: bool | None = None,
) -> dict:
    """Build HTTP request kwargs from interface, environment, and case-level overrides"""
    param_overrides = getattr(case_or_step, "param_overrides", None) or {}
    is_dict_override = isinstance(param_overrides, dict)

    # Effective values: case overrides take precedence over interface defaults
    effective_method = _override_or_default(param_overrides, "method", interface.method or "GET") if is_dict_override else (interface.method or "GET")
    effective_url = _override_or_default(param_overrides, "url", interface.url or "") if is_dict_override else (interface.url or "")
    effective_body_type = _override_or_default(param_overrides, "body_type", interface.body_type) if is_dict_override else interface.body_type

    # 请求体类型以显式配置为准：不再根据内容里的 @ 文件引用反推类型。
    # 文件引用仍然会在类型确为 form-data 时解析（见 _build_form_data_files）。
    service_key = _override_or_default(param_overrides, "service_key", getattr(interface, "service_key", None)) if is_dict_override else getattr(interface, "service_key", None)
    full_url, service = resolve_service_url(
        environment.base_url,
        effective_url,
        environment.service_config,
        service_key,
        environment.port,
    )

    active_path_params = (
        param_overrides.get("path_params")
        if is_dict_override and "path_params" in param_overrides and param_overrides["path_params"] is not None
        else getattr(interface, "path_params", None)
    )

    # Resolve path params and variables in URL
    full_url = substitute_path_params(full_url, active_path_params, variables)
    full_url = resolve_variables(full_url, variables)

    # Merge headers: env → interface → case overrides; auth injection happens after explicit headers are known.
    headers = {}
    if isinstance(environment.global_headers, dict):
        for k, v in environment.global_headers.items():
            headers[k] = v
    if is_dict_override and "headers" in param_overrides and param_overrides["headers"] is not None:
        case_headers = param_overrides["headers"]
        if isinstance(case_headers, dict):
            headers.update(case_headers)
        elif isinstance(case_headers, list):
            for h in case_headers:
                if isinstance(h, dict) and h.get("key"):
                    headers[h["key"]] = resolve_variables(str(h.get("value", "")), variables)
    elif isinstance(interface.headers, list):
        for h in interface.headers:
            if isinstance(h, dict) and h.get("key"):
                headers[h["key"]] = resolve_variables(str(h.get("value", "")), variables)

    headers = resolve_dict(headers, variables)
    explicit_auth_headers = {}
    if is_dict_override and "headers" in param_overrides and param_overrides["headers"] is not None:
        case_headers = param_overrides["headers"]
        if isinstance(case_headers, dict):
            explicit_auth_headers = case_headers
        elif isinstance(case_headers, list):
            explicit_auth_headers = {h.get("key"): h.get("value") for h in case_headers if isinstance(h, dict) and h.get("key")}
    elif isinstance(interface.headers, list):
        explicit_auth_headers = {h.get("key"): h.get("value") for h in interface.headers if isinstance(h, dict) and h.get("key")}

    auth_result = await resolve_auth_headers(
        headers=headers,
        auth_config=environment.token_config,
        service=service,
        token_fetcher=token_fetcher or _fetch_auth_token_for_execution,
        execution_context=auth_context,
        auth_cache_scope=getattr(environment, "id", None),
        explicit_auth_header=(
            explicit_auth_header
            if explicit_auth_header is not None
            else has_any_auth_header(explicit_auth_headers)
        ),
    )
    headers = auth_result.headers

    # Query params: when a case has query_params, it is the case's current query config.
    params = {}
    if is_dict_override and "query_params" in param_overrides and param_overrides["query_params"] is not None:
        override_params = param_overrides["query_params"]
        if isinstance(override_params, dict):
            params.update({k: resolve_typed_value(v, variables) for k, v in override_params.items()})
        elif isinstance(override_params, list):
            for q in override_params:
                if isinstance(q, dict) and q.get("key"):
                    params[q["key"]] = resolve_typed_value(q.get("value", ""), variables)
    elif is_dict_override and "params" in param_overrides and isinstance(param_overrides["params"], dict):
        params.update({k: resolve_typed_value(v, variables) for k, v in param_overrides["params"].items()})
    elif isinstance(interface.query_params, list):
        for q in interface.query_params:
            if isinstance(q, dict) and q.get("key"):
                params[q["key"]] = resolve_typed_value(q.get("value", ""), variables)

    # Body: use effective body_type (case overrides > interface default)
    json_data = None
    data = None
    files = None
    if effective_body_type == "json" and interface.body_content:
        try:
            json_data = resolve_json_with_typed_variables(interface.body_content, variables)
        except json.JSONDecodeError:
            data = interface.body_content
    elif effective_body_type == "form":
        data = interface.body_content
    elif effective_body_type == "form-data" and interface.body_content:
        data, files = _build_form_data_files(interface.body_content)

    # Apply case-level body/json config.
    if is_dict_override and "body_content" in param_overrides and param_overrides["body_content"] is not None:
        body_content = param_overrides.get("body_content")
        if body_content:
            if effective_body_type == "json":
                try:
                    json_data = resolve_json_with_typed_variables(str(body_content), variables)
                    data = None
                except json.JSONDecodeError:
                    data = resolve_variables(str(body_content), variables)
                    json_data = None
            elif effective_body_type == "form-data":
                data, files = _build_form_data_files(str(body_content))
            elif effective_body_type:
                data = resolve_variables(str(body_content), variables)
                json_data = None
            else:
                # 未选择请求体类型（none）：即使残留内容也不发送请求体
                data = None
                json_data = None
                files = None
        else:
            data = None
            json_data = None
            files = None
    if (
        is_dict_override
        and "json" in param_overrides
        and isinstance(param_overrides.get("json"), dict)
        and isinstance(json_data, dict)
    ):
        json_data.update(resolve_typed_dict(param_overrides["json"], variables))

    return {
        "method": effective_method.upper(),
        "url": full_url,
        "headers": headers,
        "params": params,
        "path_params": active_path_params or [],
        "body_type": effective_body_type,
        "json": json_data,
        "data": data,
        "files": files,
        "timeout": environment.timeout or 30,
        "service": service_meta(service),
        "auth_service": service,
        "auth_resolution": auth_result,
    }
