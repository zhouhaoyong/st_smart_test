"""
Audit log service for creating and managing audit logs
"""
from sqlalchemy import and_, false, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.audit_log import AuditLog
from typing import Optional, Dict, Any
from datetime import datetime
from core.timezone import beijing_now


AUDIT_MODULE_GROUPS = {
    "test_workbench": ("test_workbench",),
    "api_test": (
        "project", "environment", "interface", "testcase", "execution",
        "api_test", "api_import", "ai_import", "interface_case_generate", "executor", "parameter_set", "参数化",
    ),
    "toolbox": (
        "Xmind转换工具", "Xmind生成工具", "curl", "text_tool",
        "json_tool", "cron_tool",
    ),
    "navigation": ("navigation", "navigation_system"),
    "management": (
        "user", "ai_model", "ai_call", "ai_quota", "ai_usage", "model",
        "message_config", "notification", "feedback", "report",
        "schedule_policy", "审计日志", "data_cleanup",
    ),
}


async def create_audit_log(
    db: AsyncSession,
    user_id: int,
    user_name: str,
    module: str,
    operation: str,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    description: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """创建审计日志"""
    log = AuditLog(
        user_id=user_id,
        user_name=user_name,
        module=module,
        operation=operation,
        target_id=target_id,
        target_name=target_name,
        description=description,
        details=details,
        ip_address=ip_address,
        created_at=beijing_now(),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_audit_logs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    user_id: Optional[int] = None,
    module: str | list[str] | None = None,
    operation: str | list[str] | None = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> tuple:
    """获取审计日志列表"""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))
    base_conditions = build_audit_log_filter_conditions(
        user_id=user_id,
        module=module,
        operation=operation,
        start_time=start_time,
        end_time=end_time,
    )
    query = query.where(*base_conditions)
    count_query = count_query.where(*base_conditions)
    
    # 按时间倒序
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return logs, total


def _interface_import_log_conditions(
    project_id: int,
    operation_type: str | list[str] | None = None,
    user_id: int | None = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list:
    """构造接口操作记录的项目范围和后端筛选条件。"""
    conditions = [
        AuditLog.is_deleted.is_(False),
        AuditLog.target_id == project_id,
    ]
    source = AuditLog.details["source"].as_string()
    record_type = AuditLog.details["record_type"].as_string()
    delete_type = AuditLog.details["delete_type"].as_string()
    interface_count = AuditLog.details["interface_count"].as_integer()
    case_delete = and_(
        AuditLog.module == "api_import",
        or_(
            AuditLog.operation == "全部删除",
            record_type == "case_delete_all",
            and_(
                AuditLog.operation == "删除",
                delete_type == "cases",
                interface_count == 0,
            ),
        ),
    )
    interface_delete = and_(
        AuditLog.module == "api_import",
        AuditLog.operation == "删除",
        record_type == "interface_delete",
    )
    import_operation = and_(
        AuditLog.module == "api_import",
        AuditLog.operation.in_(('导入', '执行')),
    )
    operation_filters = [operation_type] if isinstance(operation_type, str) else list(operation_type or [])
    if operation_filters:
        type_conditions = []
        for value in dict.fromkeys(operation_filters):
            if value == "file":
                type_conditions.append(and_(
                    import_operation,
                    or_(source == "file", source.is_(None), source.not_in(("curl", "ai"))),
                ))
            elif value == "curl":
                type_conditions.append(and_(import_operation, source == "curl"))
            elif value == "ai_import":
                type_conditions.append(and_(import_operation, source == "ai"))
            elif value == "ai_generate":
                type_conditions.append(and_(
                    AuditLog.module == "interface_case_generate",
                    AuditLog.operation == "确认保存",
                ))
            elif value == "interface_delete":
                type_conditions.append(interface_delete)
            elif value == "case_delete":
                type_conditions.append(case_delete)
        conditions.append(or_(*type_conditions) if type_conditions else false())
    else:
        conditions.append(or_(
            and_(
                AuditLog.module == "api_import",
                AuditLog.operation.in_(("导入", "执行", "删除", "全部删除")),
            ),
            and_(
                AuditLog.module == "interface_case_generate",
                AuditLog.operation == "确认保存",
            ),
        ))
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if start_time:
        conditions.append(AuditLog.created_at >= start_time)
    if end_time:
        conditions.append(AuditLog.created_at <= end_time)
    return conditions


async def get_interface_import_logs(
    db: AsyncSession,
    project_id: int,
    skip: int = 0,
    limit: int = 20,
    operation_type: str | list[str] | None = None,
    user_id: int | None = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> tuple[list[AuditLog], int]:
    """获取接口管理使用的导入、生成和删除汇总日志。

    接口管理时间轴只展示最终导入、AI 生成保存和删除动作，排除文件解析、AI 分析等中间过程日志。
    target_id 统一保存项目 ID，因此无需为这类日志增加新的表或字段。
    """
    conditions = _interface_import_log_conditions(
        project_id,
        operation_type=operation_type,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
    )
    query = (
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(skip)
        .limit(limit)
    )
    count_query = select(func.count(AuditLog.id)).where(*conditions)

    result = await db.execute(query)
    logs = list(result.scalars().all())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    return logs, total


async def get_interface_import_log_operators(
    db: AsyncSession,
    project_id: int,
) -> list[dict[str, int | str]]:
    """获取当前项目操作记录中的操作人选项。"""
    query = (
        select(AuditLog.user_id, AuditLog.user_name)
        .where(*_interface_import_log_conditions(project_id))
        .group_by(AuditLog.user_id, AuditLog.user_name)
        .order_by(AuditLog.user_name.asc(), AuditLog.user_id.asc())
    )
    result = await db.execute(query)
    return [
        {"id": row.user_id, "name": row.user_name}
        for row in result.all()
        if row.user_id
    ]


async def get_interface_import_log_items(
    db: AsyncSession,
    project_id: int,
    log_id: int,
    item_type: str,
    keyword: str = "",
    skip: int = 0,
    limit: int = 10,
) -> tuple[list[dict], int] | tuple[None, int]:
    """获取接口删除或用例全部删除记录中的轻量接口或用例快照。"""
    result = await db.execute(
        select(AuditLog).where(
            AuditLog.id == log_id,
            AuditLog.is_deleted.is_(False),
            AuditLog.module == "api_import",
            AuditLog.operation.in_(("删除", "全部删除")),
            AuditLog.target_id == project_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        return None, 0

    details = log.details if isinstance(log.details, dict) else {}
    if details.get("record_type") not in {"interface_delete", "case_delete_all"}:
        return None, 0

    items_key = "interfaces" if item_type == "interfaces" else "cases"
    allowed_fields = (
        ("id", "name", "method", "url")
        if item_type == "interfaces"
        else ("id", "name", "interface_id", "interface_name", "priority")
    )
    items = [
        {field: item.get(field) for field in allowed_fields}
        for item in (details.get(items_key) or [])
        if isinstance(item, dict)
    ]
    normalized_keyword = str(keyword or "").strip().casefold()
    if normalized_keyword:
        search_fields = (
            ("name", "method", "url")
            if item_type == "interfaces"
            else ("name", "interface_name", "priority")
        )
        items = [
            item for item in items
            if normalized_keyword in " ".join(str(item.get(field) or "") for field in search_fields).casefold()
        ]

    total = len(items)
    start = max(skip, 0)
    end = start + max(limit, 1)
    return items[start:end], total


def build_audit_log_filter_conditions(
    user_id: Optional[int] = None,
    module: str | list[str] | None = None,
    operation: str | list[str] | None = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list:
    """构造审计日志统一筛选条件，查询和软删除共用。"""
    conditions = [AuditLog.is_deleted.is_(False)]
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    module_filters = [module] if isinstance(module, str) else list(module or [])
    if module_filters:
        expanded_modules = []
        for module_filter in module_filters:
            expanded_modules.extend(AUDIT_MODULE_GROUPS.get(module_filter, (module_filter,)))
        conditions.append(AuditLog.module.in_(dict.fromkeys(expanded_modules)))
    operation_filters = [operation] if isinstance(operation, str) else list(operation or [])
    if operation_filters:
        conditions.append(AuditLog.operation.in_(dict.fromkeys(operation_filters)))
    if start_time:
        conditions.append(AuditLog.created_at >= start_time)
    if end_time:
        conditions.append(AuditLog.created_at <= end_time)
    return conditions


async def soft_delete_audit_logs(
    db: AsyncSession,
    ids: list[int] | None = None,
    user_id: Optional[int] = None,
    module: str | list[str] | None = None,
    operation: str | list[str] | None = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> int:
    """软删除指定 ID 或当前筛选条件命中的审计日志。"""
    conditions = build_audit_log_filter_conditions(
        user_id=user_id,
        module=module,
        operation=operation,
        start_time=start_time,
        end_time=end_time,
    )
    if ids:
        conditions.append(AuditLog.id.in_(ids))
    result = await db.execute(
        update(AuditLog)
        .where(*conditions)
        .values(is_deleted=True, deleted_at=beijing_now())
    )
    await db.commit()
    return result.rowcount or 0
