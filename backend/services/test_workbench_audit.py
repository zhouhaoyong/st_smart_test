"""测试工作台审计快照与软删除辅助函数。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


_EXCLUDED_FIELDS = {
    "id", "created_at", "updated_at", "created_by", "updated_by",
    "is_deleted", "deleted_at", "project_id", "system_id", "version_id",
    "raw_content", "original_content", "markdown_content", "structure_json",
    "context_summary", "confirmed_facts", "open_questions", "contradictions",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def snapshot_workbench_record(record: Any) -> dict[str, Any]:
    """返回适合记录审计日志的业务字段快照，不保存大文本需求正文。"""
    if isinstance(record, dict):
        fields = record.items()
    elif hasattr(record, "__table__"):
        fields = ((column.name, getattr(record, column.name)) for column in record.__table__.columns)
    else:
        fields = vars(record).items()
    return {
        key: _json_value(value)
        for key, value in fields
        if key not in _EXCLUDED_FIELDS and not key.startswith("_")
    }


def build_change_details(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """仅记录发生变化的业务字段，便于审计页面直接阅读。"""
    changed_before: dict[str, Any] = {}
    changed_after: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        if key in _EXCLUDED_FIELDS:
            continue
        old_value = _json_value(before.get(key))
        new_value = _json_value(after.get(key))
        if old_value != new_value:
            changed_before[key] = old_value
            changed_after[key] = new_value
    return {"before": changed_before, "after": changed_after}


def soft_delete_workbench_record(record: Any, user_id: int, deleted_at: datetime) -> None:
    """统一标记测试工作台实体为已删除，禁止物理删除。"""
    record.is_deleted = True
    record.deleted_at = deleted_at
    if hasattr(record, "updated_by"):
        record.updated_by = user_id


def soft_delete_workbench_records(records: list[Any], user_id: int, deleted_at: datetime) -> None:
    """批量复用单条软删除规则，不改变调用方的级联和审计流程。"""
    for record in records:
        soft_delete_workbench_record(record, user_id, deleted_at)
