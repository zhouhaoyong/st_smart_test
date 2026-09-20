"""
Audit log utility for easy integration into endpoints
"""
from contextvars import ContextVar
from services.audit_service import create_audit_log
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, Mapping
from urllib.parse import urlsplit, urlunsplit


_INTERFACE_IMPORT_SOURCES = {"file", "curl", "ai"}
_INTERFACE_IMPORT_STATUSES = {"success", "partial", "failed"}
_SENSITIVE_IMPORT_DETAIL_KEYS = {
    "raw",
    "raw_curl",
    "file_content",
    "body_content",
    "request_body",
    "response_body",
    "headers",
}
_BATCH_AUDIT_UNITS = {
    "接口集": "个",
    "接口": "个",
    "参数集": "个",
    "用例": "条",
    "参数项": "条",
    "执行项": "条",
    "执行集": "个",
    "报告": "个",
    "需求": "条",
    "AI补全需求": "条",
    "AI合并需求": "条",
    "测试用例": "条",
    "Bug": "条",
    "系统": "个",
    "版本": "个",
    "遗留项": "条",
    "执行记录": "条",
    "发送记录": "条",
    "报告明细": "条",
    "导航应用": "个",
    "调用记录": "条",
    "审计日志": "条",
    "服务配置": "个",
    "引用": "处",
    "失败接口": "个",
    "替换": "处",
}


_current_request: ContextVar[Any] = ContextVar("audit_current_request", default=None)


def bind_audit_request(request: Any):
    """绑定当前请求，使未显式传入 request 的审计调用也能采集来源 IP。"""
    return _current_request.set(request)


def reset_audit_request(token: Any) -> None:
    """清理当前请求上下文，避免异步请求之间相互污染。"""
    _current_request.reset(token)


def _batch_audit_count_text(label: str, count: int) -> str:
    """把审计数量统一成面向业务用户的短文本。"""
    unit = _BATCH_AUDIT_UNITS.get(label, "条")
    return f"{count}{unit}{label}"


def build_project_audit_description(project_name: str | None, content: str | None) -> str:
    """生成项目内操作的统一审计文案。"""
    project_text = str(project_name or "未指定").strip()
    if not project_text.endswith("项目"):
        project_text = f"{project_text}项目"
    content_text = str(content or "").strip()
    prefix = f"{project_text}内，"
    if content_text.startswith(prefix):
        return content_text
    legacy_prefix = f"{project_text}，"
    if content_text.startswith(legacy_prefix):
        content_text = content_text[len(legacy_prefix):].lstrip()
    return f"{prefix}{content_text}"


def build_batch_audit_description(
    project_name: str | None,
    action: str,
    primary_label: str,
    primary_count: int,
    related_counts: Mapping[str, int] | None = None,
    *,
    project_internal: bool = True,
) -> str:
    """生成批量操作审计文案，只保留项目、动作和影响数量。"""
    content = f"{action}{_batch_audit_count_text(primary_label, primary_count)}"
    if project_internal:
        description = build_project_audit_description(project_name, content)
    else:
        project_text = str(project_name or "未指定").strip()
        if not project_text.endswith("项目"):
            project_text = f"{project_text}项目"
        description = f"{project_text}，{content}"
    related_text = [
        _batch_audit_count_text(label, count)
        for label, count in (related_counts or {}).items()
        if count is not None and count > 0
    ]
    if related_text:
        description += f"，其中包含{'、'.join(related_text)}"
    return description


def get_request_ip(request: Any = None) -> Optional[str]:
    """提取请求来源 IP，不读取或记录请求中的敏感内容。"""
    if request is None:
        request = _current_request.get()
    if request is None:
        return None
    headers = getattr(request, "headers", None)
    forwarded_for = headers.get("X-Forwarded-For") if headers else None
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    real_ip = headers.get("X-Real-IP") if headers else None
    if real_ip:
        return real_ip.strip() or None
    client = getattr(request, "client", None)
    return getattr(client, "host", None)


def _strip_url_credentials(value: str) -> str:
    """移除 URL authority 中的用户名和密码，并去掉查询参数与片段。"""
    clean = value.split("?", 1)[0].split("#", 1)[0]
    scheme_separator = clean.find("://")
    if scheme_separator >= 0:
        authority_start = scheme_separator + 3
    elif clean.startswith("//"):
        authority_start = 2
    else:
        return clean
    path_start = clean.find("/", authority_start)
    authority_end = path_start if path_start >= 0 else len(clean)
    authority = clean[authority_start:authority_end]
    if "@" not in authority:
        return clean
    return clean[:authority_start] + authority.rsplit("@", 1)[-1] + clean[authority_end:]


def safe_url_target(value: Any, max_length: int = 200) -> Optional[str]:
    """仅保留 URL 的协议、主机和路径，避免把认证信息写入日志。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = _strip_url_credentials(text)
    try:
        parsed = urlsplit(text)
        text = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except ValueError:
        # 对格式异常的 URL 也至少移除查询参数、片段和 authority 凭据。
        text = _strip_url_credentials(text)
    return text[:max_length]


def safe_host_target(value: Any, max_length: int = 100) -> Optional[str]:
    """仅保留 URL 的主机名，丢弃协议、路径、查询参数和认证信息。

    审计日志面向业务用户，完整地址属于敏感调试信息，不应落库；主机名足以回溯
    「调的是哪个服务」，因此统一用它作为操作对象。
    """
    safe = safe_url_target(value)
    if not safe:
        return None
    try:
        host = urlsplit(safe).netloc
    except ValueError:
        host = ""
    if not host and not safe.startswith("/"):
        # 用户漏填协议时（如 api.example.com/v1/login），只取第一个斜杠前的主机部分；
        # 相对地址（如 /api/login）不保留任何路径信息。
        host = safe.split("/", 1)[0]
    if not host:
        return None
    return host.split("@")[-1][:max_length] or None


def build_interface_delete_details(
    interfaces: list[Any],
    cases: list[Any],
    delete_type: str,
) -> Dict[str, Any]:
    """生成接口删除记录所需的轻量快照，不保存请求体等接口详情。"""
    interface_items = [
        {
            "id": interface.id,
            "name": interface.name,
            "method": interface.method,
            "url": safe_url_target(interface.url, max_length=500),
        }
        for interface in interfaces
    ]
    interface_names = {item["id"]: item["name"] for item in interface_items}
    case_items = [
        {
            "id": case.id,
            "name": case.name,
            "interface_id": case.interface_id,
            "interface_name": interface_names.get(case.interface_id),
            "priority": case.priority,
        }
        for case in cases
    ]
    interface_count = len(interface_items)
    case_count = len(case_items)
    return {
        "record_type": "interface_delete",
        "delete_type": delete_type,
        "status": "success",
        "interface_count": interface_count,
        "case_count": case_count,
        "summary": f"接口：删除 {interface_count} 个；用例：删除 {case_count} 个",
        "interfaces": interface_items,
        "cases": case_items,
    }


def merge_interface_delete_details(details_list: list[Dict[str, Any]], delete_type: str) -> Dict[str, Any]:
    """合并同一次批量删除产生的快照，并按资源 ID 去重。"""
    interfaces_by_id: dict[Any, dict] = {}
    cases_by_id: dict[Any, dict] = {}
    for details in details_list or []:
        for item in details.get("interfaces") or []:
            if item.get("id") is not None:
                interfaces_by_id.setdefault(item["id"], dict(item))
        for item in details.get("cases") or []:
            if item.get("id") is not None:
                cases_by_id.setdefault(item["id"], dict(item))

    interface_items = list(interfaces_by_id.values())
    interface_names = {item["id"]: item.get("name") for item in interface_items}
    case_items = list(cases_by_id.values())
    for item in case_items:
        if item.get("interface_id") in interface_names:
            item["interface_name"] = interface_names[item["interface_id"]]

    return {
        "record_type": "interface_delete",
        "delete_type": delete_type,
        "status": "success",
        "interface_count": len(interface_items),
        "case_count": len(case_items),
        "summary": f"接口：删除 {len(interface_items)} 个；用例：删除 {len(case_items)} 个",
        "interfaces": interface_items,
        "cases": case_items,
    }


async def log_operation(
    db: AsyncSession,
    user_id: int,
    user_name: str,
    module: str,
    operation: str,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    description: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    request: Any = None,
):
    """记录操作日志（异步，不阻塞主流程）"""
    try:
        if ip_address is None:
            ip_address = get_request_ip(request)
        await create_audit_log(
            db=db,
            user_id=user_id,
            user_name=user_name,
            module=module,
            operation=operation,
            target_id=target_id,
            target_name=target_name,
            description=description,
            details=details,
            ip_address=ip_address,
        )
    except Exception:
        # 日志记录失败不应影响主业务
        pass


async def log_user_operation(
    db: AsyncSession,
    user: Any,
    module: str,
    operation: str,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    description: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Any = None,
):
    """使用当前用户记录业务操作，统一补充来源 IP。"""
    if not user or not getattr(user, "id", None):
        return
    await log_operation(
        db=db,
        user_id=user.id,
        user_name=getattr(user, "real_name", None) or getattr(user, "phone", "用户"),
        module=module,
        operation=operation,
        target_id=target_id,
        target_name=target_name,
        description=description,
        details=details,
        ip_address=get_request_ip(request),
    )


def _sanitize_import_details(value: Any) -> Any:
    """递归移除导入原文和请求内容，避免时间轴日志记录敏感数据。"""
    if isinstance(value, dict):
        return {
            key: _sanitize_import_details(item)
            for key, item in value.items()
            if str(key).strip().lower() not in _SENSITIVE_IMPORT_DETAIL_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_import_details(item) for item in value]
    return value


async def log_interface_import(
    db: AsyncSession,
    user: Any,
    project_id: int,
    project_name: Optional[str],
    source: str,
    status: str,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
    source_name: Optional[str] = None,
    request: Any = None,
):
    """记录一次接口导入汇总，不记录解析预览和原始请求内容。"""
    normalized_source = str(source or "").strip().lower()
    if normalized_source not in _INTERFACE_IMPORT_SOURCES:
        normalized_source = "file"
    normalized_status = str(status or "").strip().lower()
    if normalized_status not in _INTERFACE_IMPORT_STATUSES:
        normalized_status = "failed"

    payload = _sanitize_import_details(dict(details or {}))
    payload.update({
        "interface_import": True,
        "source": normalized_source,
        "source_name": (str(source_name).strip()[:200] if source_name else None),
        "status": normalized_status,
        "summary": str(summary or "接口导入")[:500],
    })
    await log_user_operation(
        db=db,
        user=user,
        module="api_import",
        operation="导入",
        target_id=project_id,
        target_name=project_name,
        description=build_project_audit_description(project_name, payload["summary"]),
        details=payload,
        request=request,
    )
