"""
请求执行器 API — 调试、运行单用例 / 多用例
所有接口请求在后端发出，避免浏览器跨域
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form
from copy import deepcopy
import os
import time
import uuid
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import List
from db.session import get_db
from models.models import User, Environment, Interface, InterfaceCollection, Project
from core.security import get_current_active_user
from core.permissions import can_view_project_details, ensure_project_asset_manage, is_manager
from core.response import MASKED_VALUE, mask_sensitive_data, mask_sensitive_text, success_response, UnifiedException
from utils.audit_logger import (
    build_project_audit_description,
    log_user_operation,
    safe_host_target,
)
from services.auth_token import AuthTokenError, fetch_auth_token
from services.auth_config import has_any_auth_header
from services.execution_engine.runner import build_execution_global_vars, execute_step

router = APIRouter(prefix="/executor", tags=["请求执行器"])

logger = logging.getLogger(__name__)


def _sanitize_body(val):
    """过滤空值 body：None / 空字符串 / 空白 / null / none / undefined 均视为无 body"""
    if val is None:
        return None
    if not isinstance(val, str):
        return val
    v = val.strip()
    if not v or v.lower() in ('null', 'none', 'undefined'):
        return None
    return v


def build_runtime_interface(data: dict | None):
    """把尚未落库的 AI 预览接口转换为执行器可读取的接口对象。"""
    source = data if isinstance(data, dict) else {}
    return SimpleNamespace(
        id=None,
        name=source.get("name") or "预览用例",
        method=source.get("method") or "GET",
        url=source.get("url") or "",
        service_key=source.get("service_key"),
        headers=source.get("headers") or [],
        query_params=source.get("query_params") or [],
        path_params=source.get("path_params") or [],
        body_type=source.get("body_type") or "",
        body_content=source.get("body_content") or "",
        body_schema_types=source.get("body_schema_types") or {},
        pre_script=source.get("pre_script") or "",
        post_script=source.get("post_script") or "",
    )


def _format_runtime_step_result(result: dict, step_name: str) -> dict:
    """把执行引擎的单步结果适配为运行用例接口的历史结构。"""
    request_data = result.get("request_data") or {}
    response_data = result.get("response_data") or {}
    status_code = response_data.get("status_code", 0)
    status = result.get("status", "failed")
    if status != "success" and not response_data and result.get("error_message"):
        status = "error"
    diffs = result.get("diff_result") or []
    assertion_results = result.get("assertion_results")
    if not isinstance(assertion_results, dict):
        assertion_results = {"passed": 0, "failed": 0, "diffs": diffs}

    if status == "success":
        message = f"HTTP {status_code} ({result.get('duration', 0)}ms) — 断言全部通过"
    else:
        message_parts = [result.get("error_message") or ""]
        for diff in diffs:
            message_parts.append(
                f"{diff.get('expression', diff.get('type', ''))}: "
                f"期望={diff.get('expected', '')} 实际={diff.get('actual', '')}"
            )
        message = " | ".join(filter(None, message_parts)) or "执行失败"

    return {
        "name": step_name,
        "status": status,
        "msg": message,
        "statusCode": status_code,
        "duration": result.get("duration", 0),
        "request": _runtime_request_payload(request_data),
        "response": {
            "status_code": status_code,
            "headers": response_data.get("headers", {}),
            "body": response_data.get("json") if response_data.get("json") is not None else response_data.get("text", ""),
            "text": response_data.get("text", ""),
        },
        "assertion_results": assertion_results,
        "logs": result.get("logs", ""),
    }


def _format_runtime_debug_result(result: dict) -> dict:
    """把执行引擎结果适配为调试接口的历史响应结构。"""
    request_data = result.get("request_data") or {}
    response_data = result.get("response_data") or {}
    status_code = response_data.get("status_code", 0)
    assertion_results = result.get("assertion_results")
    if not isinstance(assertion_results, dict):
        assertion_results = {"passed": 0, "failed": 0, "diffs": result.get("diff_result") or []}

    has_response = bool(response_data)
    status = result.get("status", "failed")
    if status != "success" and not has_response:
        status = "error"
    response = None
    if has_response:
        response_text = response_data.get("text", "")
        response = {
            "status_code": status_code,
            "headers": response_data.get("headers", {}),
            "body": (
                response_data.get("json")
                if response_data.get("json") is not None
                else response_text[:10000]
            ),
            "text": response_text[:10000],
        }

    formatted = {
        "success": status == "success",
        "request": _runtime_request_payload(request_data),
        "response": response,
        "duration": result.get("duration", 0),
        "status": status,
        "status_code": status_code,
        "assertion_results": assertion_results,
        "fail_msg": "断言未通过" if assertion_results.get("failed", 0) else "",
        # 前置/后置脚本日志，与运行用例的单步结果保持一致
        "logs": result.get("logs", ""),
    }
    if result.get("error_message"):
        formatted["error"] = result["error_message"]
    return formatted


def _build_execution_audit_description(
    project_name: str | None,
    execution_type: str,
    target_name: str | None,
    status: str | None,
) -> str:
    """生成接口调试和用例运行的统一审计内容。"""
    action_label = {
        "interface": "接口调试",
        "case": "用例运行",
    }.get(execution_type, "执行")
    target_label = str(target_name or "").strip()[:200]
    target_suffix = f"：{target_label}" if target_label else ""
    result_label = "成功" if status == "success" else "失败"
    return build_project_audit_description(
        project_name,
        f"{action_label}{target_suffix}，{result_label}",
    )


def _runtime_request_payload(request_data: dict) -> dict:
    payload = {
        key: request_data.get(key)
        for key in ("method", "url", "headers", "params", "path_params", "body", "proxy", "service")
    }
    if "files" in request_data:
        payload["files"] = request_data["files"]
    return payload


def _mask_execution_part(value):
    if isinstance(value, dict):
        masked = mask_sensitive_data(value)
        for field in ("body", "text"):
            if field in masked and isinstance(value.get(field), str):
                masked[field] = mask_sensitive_text(value[field])
        return masked
    if isinstance(value, str):
        return mask_sensitive_text(value)
    return value


def _mask_execution_result(
    result: dict,
    current_user: User,
    *,
    reveal_sensitive: bool = False,
) -> dict:
    """普通用户查看执行结果时，保留结构但不返回敏感明文。"""
    if reveal_sensitive or is_manager(current_user) or not isinstance(result, dict):
        return result
    safe_result = deepcopy(result)
    if isinstance(safe_result.get("steps"), list):
        safe_result["steps"] = [
            _mask_execution_result(step, current_user, reveal_sensitive=reveal_sensitive)
            for step in safe_result["steps"]
        ]
    for field in ("request", "response"):
        if field in safe_result:
            safe_result[field] = _mask_execution_part(safe_result[field])
    if safe_result.get("assertion_results") and isinstance(safe_result["assertion_results"], dict):
        diffs = safe_result["assertion_results"].get("diffs") or []
        for diff in diffs:
            if isinstance(diff, dict):
                if diff.get("expected") not in (None, ""):
                    diff["expected"] = MASKED_VALUE
                if diff.get("actual") not in (None, ""):
                    diff["actual"] = MASKED_VALUE
    if safe_result.get("fail_msg"):
        safe_result["fail_msg"] = "断言未通过"
    if "msg" in safe_result:
        safe_result["msg"] = "执行成功" if safe_result.get("status") == "success" else "执行失败"
    if safe_result.get("logs"):
        safe_result["logs"] = MASKED_VALUE
    return safe_result


async def _fetch_auth_token(auth: dict, auth_key: str | None = None) -> str | None:
    try:
        return await fetch_auth_token(auth, auth_key)
    except AuthTokenError as exc:
        raise UnifiedException(code=400, message=str(exc)) from exc


# ====== Temp File Upload (form-data support) ======

TEMP_UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'uploads', 'temp'))
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
TEMP_UPLOAD_MAX_SIZE = 10 * 1024 * 1024


def validate_temp_upload_size(size: int) -> None:
    """校验执行临时文件大小，避免大文件占满服务内存和磁盘。"""
    if size > TEMP_UPLOAD_MAX_SIZE:
        raise UnifiedException(code=400, message="文件大小不能超过10MB")


async def _read_temp_upload(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await file.read(min(1024 * 1024, TEMP_UPLOAD_MAX_SIZE - total_size + 1))
        if not chunk:
            break
        total_size += len(chunk)
        validate_temp_upload_size(total_size)
        chunks.append(chunk)
    return b''.join(chunks)


def _cleanup_local_temp_files(keep_minutes: int = 1440):
    """Remove local temp files older than keep_minutes (OSS files managed separately)."""
    try:
        cutoff = time.time() - keep_minutes * 60
        for name in os.listdir(TEMP_UPLOAD_DIR):
            fpath = os.path.join(TEMP_UPLOAD_DIR, name)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                try:
                    os.remove(fpath)
                except OSError:
                    pass
    except Exception:
        pass


@router.post("/upload-file")
async def upload_temp_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload temp file for form-data. Uses OSS in production, local disk in dev."""
    _cleanup_local_temp_files()

    file_bytes = await _read_temp_upload(file)
    safe_name = (file.filename or 'upload.tmp').replace('\\', '/').rsplit('/', 1)[-1]
    ext = os.path.splitext(safe_name)[1].lower()

    # Determine content type
    _MIME_MAP = {'.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                 '.xls': 'application/vnd.ms-excel', '.pdf': 'application/pdf',
                 '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                 '.csv': 'text/csv', '.txt': 'text/plain', '.zip': 'application/zip'}
    content_type = _MIME_MAP.get(ext) or 'application/octet-stream'

    # Use OSS if enabled, otherwise local disk
    from utils.oss_client import upload_file as oss_upload, _get_oss_client as _get_oss

    oss = _get_oss()
    if oss:
        # 上传到 OSS，支持容器化部署
        object_key = oss_upload(file_bytes, 'temp', safe_name, content_type)
        filepath = os.path.join(TEMP_UPLOAD_DIR, f"{uuid.uuid4().hex[:12]}_{safe_name}")
        # Also save locally for fast access during the same session
        with open(filepath, 'wb') as f:
            f.write(file_bytes)
        ref = f"@oss:{object_key}"  # OSS reference (persistent)
        response_file_path = ref
    else:
        # Local dev — save to disk
        unique_id = uuid.uuid4().hex[:12]
        stored_name = f"{unique_id}_{safe_name}"
        filepath = os.path.join(TEMP_UPLOAD_DIR, stored_name)
        with open(filepath, 'wb') as f:
            f.write(file_bytes)
        ref = f"@temp:{stored_name}"  # opaque local temp reference
        response_file_path = ref

    await log_user_operation(
        db=db,
        user=current_user,
        module="executor",
        operation="上传",
        target_name=safe_name,
        description="上传执行临时文件",
        details={"file_size": len(file_bytes), "extension": ext},
    )

    return success_response(data={
        "file_path": response_file_path,
        "file_name": safe_name,
        "file_size": len(file_bytes),
        "ref": ref,
    })


# ====== Schemas ======

class DebugRequest(BaseModel):
    """调试请求"""
    method: str = "GET"
    url: str
    base_url: str
    port: int | None = None
    headers: dict = Field(default_factory=dict)
    body: str | None = None
    params: dict = Field(default_factory=dict)
    timeout: int = 30
    environment_id: int | None = None
    parameter_set_id: int | None = None
    interface_id: int | None = None
    path_params: list | None = None
    service_key: str | None = None
    pre_script: str | None = None
    post_script: str | None = None
    body_type: str | None = None  # json | form | form-data | raw


class StepRunConfig(BaseModel):
    """单步骤运行配置"""
    step_order: int = 1
    interface_id: int
    param_overrides: dict = Field(default_factory=dict)
    assertions: list = Field(default_factory=list)


class RunCaseRequest(BaseModel):
    """运行用例请求"""
    environment_id: int
    parameter_set_id: int | None = None
    interface_id: int | None = None
    interface_data: dict | None = None
    test_case_name: str | None = None
    param_overrides: dict = Field(default_factory=dict)
    assertions: list = Field(default_factory=list)
    script: str | None = None
    steps: List[StepRunConfig] = Field(default_factory=list)


def _resolve_run_items(data: RunCaseRequest) -> list[StepRunConfig]:
    """统一解析单用例运行请求；空请求不再被当成成功执行。"""
    if data.steps:
        return list(data.steps)
    if data.interface_id or data.interface_data:
        return [
            StepRunConfig(
                step_order=1,
                interface_id=data.interface_id or 0,
                param_overrides=data.param_overrides or {},
                assertions=data.assertions,
            )
        ]
    return []


def _build_debug_files(data: DebugRequest) -> dict | None:
    """Parse form-data body for file references and build httpx files dict.

    Delegates to the shared _build_form_data_files in execution_engine
    to avoid duplicating base64/OSS/file-path parsing and path translation.
    """
    if data.body_type != "form-data" or not data.body:
        return None
    from services.execution_engine.request_builder import _build_form_data_files
    _, files = _build_form_data_files(data.body)
    return files


# ====== 调试 ======


def _build_debug_environment(data: DebugRequest, environment):
    """为无环境调试补齐执行引擎所需的最小运行时环境。"""
    if environment is not None:
        return environment
    return SimpleNamespace(
        id=None,
        base_url=data.base_url,
        port=data.port,
        timeout=data.timeout,
        global_variables={},
        global_headers={},
        service_config={},
        token_config={},
        proxy_config={},
        proxy_http=None,
        proxy_https=None,
    )


def _build_debug_interface(
    data: DebugRequest,
    source_interface,
    *,
    path_params: list,
    service_key: str | None,
    pre_script: str | None,
    post_script: str | None,
):
    body = _sanitize_body(data.body)
    # 请求体类型以显式选择为准：未选择类型（none）即不发送请求体，不再按内容猜测类型
    body_type = data.body_type or ""
    return build_runtime_interface({
        "name": getattr(source_interface, "name", None) or "调试接口",
        "method": data.method,
        "url": data.url,
        "headers": [
            {"key": str(key), "value": value}
            for key, value in (data.headers or {}).items()
            if str(key).strip() and value is not None and value != ""
        ],
        "query_params": [
            {"key": str(key), "value": value}
            for key, value in (data.params or {}).items()
            if str(key).strip() and value is not None
        ],
        "path_params": path_params or [],
        "body_type": body_type or "",
        "body_content": body or "",
        "service_key": service_key,
        "pre_script": pre_script or "",
        "post_script": post_script or "",
    })

@router.post("/debug")
async def debug_request(
    data: DebugRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """调试：发送单次接口请求，返回请求/响应数据"""
    if not data.environment_id and not data.interface_id and not is_manager(current_user):
        raise UnifiedException(code=403, message="权限不足")

    # 解析环境全局变量（支持 $.variable 和 {{variable}}）
    global_vars = {}
    env = None
    detail_project = None
    user_debug_auth_header = has_any_auth_header(data.headers)
    auth_context = {"tokens": {}}
    if data.environment_id:
        env_result = await db.execute(select(Environment).where(Environment.id == data.environment_id, Environment.is_deleted == False))
        env = env_result.scalar_one_or_none()
        if not env:
            raise UnifiedException(code=400, message="执行环境不存在")
        project_result = await db.execute(
            select(Project).where(Project.id == env.project_id, Project.is_deleted == False)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise UnifiedException(code=403, message="权限不足")
        ensure_project_asset_manage(current_user, project)
        detail_project = project
        global_vars = await build_execution_global_vars(db, env, data.parameter_set_id)

    interface_path_params = []
    interface_service_key = data.service_key
    source_interface = None
    pre_script = data.pre_script
    post_script = data.post_script
    if data.interface_id:
        iface_result = await db.execute(
            select(Interface).where(Interface.id == data.interface_id, Interface.is_deleted == False)
        )
        iface = iface_result.scalar_one_or_none()
        if not iface:
            raise UnifiedException(code=400, message="调试接口不存在")
        iface_project_result = await db.execute(
            select(Project)
            .join(InterfaceCollection, InterfaceCollection.project_id == Project.id)
            .where(
                InterfaceCollection.id == iface.collection_id,
                InterfaceCollection.is_deleted == False,
                Project.is_deleted == False,
            )
        )
        iface_project = iface_project_result.scalar_one_or_none()
        if not iface_project:
            raise UnifiedException(code=403, message="权限不足")
        ensure_project_asset_manage(current_user, iface_project)
        detail_project = iface_project
        if env and env.project_id != iface_project.id:
            raise UnifiedException(code=400, message="调试接口与执行环境不属于同一项目")
        source_interface = iface
        interface_service_key = data.service_key if data.service_key is not None else getattr(iface, "service_key", None)
        interface_path_params = data.path_params if data.path_params is not None else (getattr(iface, "path_params", None) or [])
        if pre_script is None:
            pre_script = getattr(iface, "pre_script", None)
        if post_script is None:
            post_script = getattr(iface, "post_script", None)

    runtime_environment = _build_debug_environment(data, env)
    runtime_interface = _build_debug_interface(
        data,
        source_interface,
        path_params=interface_path_params,
        service_key=interface_service_key,
        pre_script=pre_script,
        post_script=post_script,
    )
    runtime_result = await execute_step(
        interface=runtime_interface,
        environment=runtime_environment,
        case_or_step=SimpleNamespace(param_overrides={}, assertions=[], script=None),
        global_vars=global_vars,
        step_order=1,
        auth_context=auth_context,
        token_fetcher=_fetch_auth_token,
        explicit_auth_header=user_debug_auth_header,
        propagate_business_errors=True,
    )
    result = _format_runtime_debug_result(runtime_result)
    response_meta = result.get("response") if isinstance(result, dict) else None
    audit_target_name = (
        getattr(source_interface, "name", None)
        or safe_host_target(data.url)
        or "临时请求"
    )[:200]
    audit_status = result.get("status") if isinstance(result, dict) else None
    await log_user_operation(
        db=db,
        user=current_user,
        module="executor",
        operation="接口调试",
        # 审计不写完整地址：优先用接口名，其次只保留主机名。
        target_name=audit_target_name,
        description=_build_execution_audit_description(
            getattr(detail_project, "name", None),
            "interface",
            audit_target_name,
            audit_status,
        ),
        details={
            "status": audit_status,
            "status_code": response_meta.get("status_code") if isinstance(response_meta, dict) else None,
            "execution_type": "interface",
            "audit_content_version": 2,
        },
    )
    return success_response(data=_mask_execution_result(
        result,
        current_user,
        reveal_sensitive=can_view_project_details(current_user, detail_project),
    ))


# ====== 运行用例 ======

@router.post("/run-case")
async def run_test_case(
    data: RunCaseRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """运行用例：优先使用用例级配置，兼容旧 steps 调用"""
    # 获取环境
    env_result = await db.execute(select(Environment).where(Environment.id == data.environment_id, Environment.is_deleted == False))
    env = env_result.scalar_one_or_none()
    if not env:
        raise UnifiedException(code=400, message="环境不存在")
    project_result = await db.execute(
        select(Project).where(Project.id == env.project_id, Project.is_deleted == False)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise UnifiedException(code=403, message="权限不足")
    ensure_project_asset_manage(current_user, project)

    global_vars = await build_execution_global_vars(db, env, data.parameter_set_id)
    auth_context = {"tokens": {}}

    step_results = []
    total_passed = 0
    total_failed = 0
    executed_interface_names = []

    run_items = _resolve_run_items(data)
    if not run_items:
        raise UnifiedException(code=400, message="没有可执行的接口或用例")

    for step_cfg in run_items:
        overrides = step_cfg.param_overrides or {}
        iface_result = await db.execute(
            select(Interface).options(selectinload(Interface.collection)).where(
                Interface.id == step_cfg.interface_id,
                Interface.is_deleted == False,
            )
        )
        interface = iface_result.scalar_one_or_none()
        if not interface and data.interface_data and not data.interface_id:
            interface = build_runtime_interface(data.interface_data)
        if not interface and step_cfg.interface_id:
            raise UnifiedException(code=400, message="执行接口不存在")
        if interface and not isinstance(interface, SimpleNamespace):
            collection = interface.collection
            if not collection or collection.is_deleted or collection.project_id != env.project_id:
                raise UnifiedException(code=400, message="执行接口与环境不属于同一项目")
        if interface and getattr(interface, "name", None):
            executed_interface_names.append(interface.name)
        if not interface:
            interface = build_runtime_interface({
                "method": overrides.get("_method", "GET"),
                "url": overrides.get("_url", "/"),
                "service_key": overrides.get("service_key"),
            })
            interface.name = None

        case_or_step = SimpleNamespace(
            param_overrides=overrides,
            assertions=step_cfg.assertions,
            script=data.script,
        )
        runtime_result = await execute_step(
            interface=interface,
            environment=env,
            case_or_step=case_or_step,
            global_vars=global_vars,
            step_order=step_cfg.step_order,
            auth_context=auth_context,
            token_fetcher=_fetch_auth_token,
        )
        script_variables = runtime_result.get("script_variables") or {}
        if isinstance(script_variables, dict):
            global_vars.update(script_variables)

        step_name = getattr(interface, "name", None) or (
            overrides.get("_method", "GET") + " " + overrides.get("_url", "/")
        )
        step_results.append(_format_runtime_step_result(runtime_result, step_name))
        if runtime_result.get("status") == "success":
            total_passed += 1
        else:
            total_failed += 1

    run_result = {
        "steps": step_results,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "status": "success" if total_failed == 0 else "failed",
    }
    audit_target_name = (data.test_case_name or "").strip()[:200] or None
    await log_user_operation(
        db=db,
        user=current_user,
        module="executor",
        operation="用例运行",
        target_name=audit_target_name,
        description=_build_execution_audit_description(
            getattr(project, "name", None),
            "case",
            audit_target_name,
            run_result["status"],
        ),
        details={
            "status": run_result["status"],
            "execution_count": len(step_results),
            "successful_executions": total_passed,
            "failed_executions": total_failed,
            "execution_type": "case",
            "audit_content_version": 2,
        },
    )
    return success_response(data=_mask_execution_result(
        run_result,
        current_user,
        reveal_sensitive=can_view_project_details(current_user, project),
    ))
