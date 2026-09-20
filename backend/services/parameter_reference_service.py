"""参数引用检索 / 替换 / 去参数化的纯逻辑与数据访问。

从 api/v1/endpoints/parameter_sets.py 逐段搬运而来，接口层调用本模块，
不改变任何行为。
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from services.parameter_typing import infer_param_type


def _truncate(text: str, search: str, context: int = 40) -> str:
    idx = text.find(search)
    if idx < 0:
        return text[:80]
    start = max(0, idx - context)
    end = min(len(text), idx + len(search) + context)
    return text[start:end]


def _parameter_reference_tokens(key: str) -> tuple[str, str]:
    return (f"$.{key}", "{{" + key + "}}")


def _replace_parameter_reference_tokens(value, key: str, replacement: str):
    tokens = _parameter_reference_tokens(key)
    if isinstance(value, str):
        result = value
        for token in tokens:
            result = result.replace(token, replacement)
        return result
    return value


def _contains_parameter_reference(value, key: str) -> bool:
    if value is None:
        return False
    tokens = _parameter_reference_tokens(key)
    if isinstance(value, str):
        return any(token in value for token in tokens)
    if isinstance(value, dict):
        return any(_contains_parameter_reference(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_contains_parameter_reference(v, key) for v in value)
    return any(token in str(value) for token in tokens)


def _append_param_list_references(refs: list[dict], source_type: str, source_id: int, source_name: str, prefix: str, label: str, values, key: str):
    for i, item in enumerate(values or []):
        if _contains_parameter_reference(item.get("value"), key):
            refs.append({
                "source_type": source_type,
                "source_id": source_id,
                "source_name": source_name,
                "field_path": f"{prefix}.{i}.value",
                "match_type": f"{label} {item.get('key', '')}".strip(),
                "value": str(item.get("value", "")),
            })


def _find_references_in_record(source_type: str, record, key: str) -> list[dict]:
    refs: list[dict] = []
    if source_type == "interface":
        source_id = record.id
        source_name = f"{getattr(record, 'method', '')} {getattr(record, 'url', '')}".strip() or getattr(record, "name", "")
        _append_param_list_references(refs, source_type, source_id, source_name, "headers", "请求头", getattr(record, "headers", []) or [], key)
        _append_param_list_references(refs, source_type, source_id, source_name, "query_params", "查询参数", getattr(record, "query_params", []) or [], key)
        _append_param_list_references(refs, source_type, source_id, source_name, "path_params", "路径参数", getattr(record, "path_params", []) or [], key)
        body_content = getattr(record, "body_content", None)
        if _contains_parameter_reference(body_content, key):
            refs.append({
                "source_type": source_type,
                "source_id": source_id,
                "source_name": source_name,
                "field_path": "body_content",
                "match_type": "请求体",
                "value": _truncate(str(body_content), f"$.{key}"),
            })
    elif source_type == "testcase":
        source_id = record.id
        source_name = getattr(record, "name", "")
        overrides = getattr(record, "param_overrides", {}) or {}
        _append_param_list_references(refs, source_type, source_id, source_name, "param_overrides.headers", "用例请求头", overrides.get("headers", []) or [], key)
        _append_param_list_references(refs, source_type, source_id, source_name, "param_overrides.query_params", "用例查询参数", overrides.get("query_params", []) or [], key)
        _append_param_list_references(refs, source_type, source_id, source_name, "param_overrides.path_params", "用例路径参数", overrides.get("path_params", []) or [], key)
        body_content = overrides.get("body_content")
        if _contains_parameter_reference(body_content, key):
            refs.append({
                "source_type": source_type,
                "source_id": source_id,
                "source_name": source_name,
                "field_path": "param_overrides.body_content",
                "match_type": "用例请求体",
                "value": _truncate(str(body_content), f"$.{key}"),
            })
    return refs


def _json_match_value(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _json_key_matches(
    raw: str | None,
    match_key: str | None,
    prefix: str,
    param_type: str | None = None,
    schema_types: dict[str, str] | None = None,
):
    if not raw or not match_key:
        return []
    try:
        obj = json.loads(raw)
    except Exception:
        return []

    matches = []
    schema_types = schema_types or {}

    def walk(value, path):
        if isinstance(value, dict):
            for k, v in value.items():
                next_path = [*path, k]
                if k == match_key:
                    key_path = ".".join(next_path)
                    schema_type = schema_types.get(key_path)
                    actual_type = schema_type or infer_param_type(v)
                    if param_type and actual_type != param_type:
                        matches.append({
                            "field": f"{prefix}[{'.'.join(next_path)}]",
                            "path": f"{prefix}.{'.'.join(next_path)}",
                            "value": _json_match_value(v),
                            "match_type": f"请求体字段 {k}",
                            "actual_type": actual_type,
                            "expected_type": param_type,
                            "conflict_kind": "type_mismatch",
                            "conflict_reason": f"类型不匹配：参数 {match_key} 为 {param_type}，接口字段 {'.'.join(next_path)} 为 {actual_type}",
                        })
                    elif schema_type or not isinstance(v, (dict, list)) or param_type in {"list", "object"}:
                        matches.append({
                            "field": f"{prefix}[{'.'.join(next_path)}]",
                            "path": f"{prefix}.{'.'.join(next_path)}",
                            "value": _json_match_value(v),
                            "match_type": f"请求体字段 {k}",
                            "actual_type": actual_type,
                            "expected_type": param_type,
                        })
                    continue
                walk(v, next_path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, [*path, str(i)])

    walk(obj, [])
    return matches


def _body_matches_for_parameterize(
    raw: str | None,
    search_value: str,
    match_key: str | None,
    field_prefix: str,
    raw_match_type: str = "请求体",
    param_type: str | None = None,
    schema_types: dict[str, str] | None = None,
):
    if not raw:
        return []

    if match_key:
        return _json_key_matches(raw, match_key, f"{field_prefix}_json", param_type, schema_types)

    if search_value and search_value in raw:
        return [{
            "field": field_prefix,
            "path": field_prefix,
            "value": _truncate(raw, search_value),
            "match_type": raw_match_type,
        }]
    return []


def _pair_matches_for_parameterize(key: str, value: str, search_value: str, match_key: str | None) -> bool:
    """When a parameter key is known, only that key should be parameterized."""
    if match_key:
        return key == match_key
    return bool(search_value and search_value in value)


def _replace_json_path(raw: str | None, path_parts: list[str], new_val: str) -> str | None:
    if raw is None:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return raw
    cursor = obj
    for part in path_parts[:-1]:
        if isinstance(cursor, list) and part.isdigit():
            idx = int(part)
            if idx >= len(cursor):
                return raw
            cursor = cursor[idx]
        elif isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            return raw
    last = path_parts[-1] if path_parts else None
    if isinstance(cursor, list) and last and last.isdigit():
        idx = int(last)
        if idx < len(cursor):
            cursor[idx] = new_val
    elif isinstance(cursor, dict) and last in cursor:
        cursor[last] = new_val
    else:
        return raw
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _replace_raw_text_for_parameterize(raw: str | None, search_value: str, new_val: str) -> str | None:
    if raw is None:
        return None
    if not search_value:
        return raw
    return raw.replace(search_value, new_val)


def _deparameterize_list_values(values, key: str, replacement: str):
    changed = False
    result = []
    for item in values or []:
        next_item = dict(item)
        old_value = next_item.get("value")
        new_value = _replace_parameter_reference_tokens(old_value, key, replacement)
        if new_value != old_value:
            next_item["value"] = new_value
            changed = True
        result.append(next_item)
    return result, changed


def _parameter_value_for_json(replacement: str, param_type: str | None):
    """将参数集中的字符串值恢复成请求体 JSON 需要的原生类型。"""
    param_type = param_type or "string"
    text = "" if replacement is None else str(replacement).strip()
    try:
        if param_type == "int":
            return int(text)
        if param_type == "float":
            return float(text)
        if param_type == "bool":
            return text.lower() == "true"
        if param_type in {"list", "object"}:
            parsed = json.loads(text)
            if param_type == "list" and isinstance(parsed, list):
                return parsed
            if param_type == "object" and isinstance(parsed, dict):
                return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return replacement


def _replace_json_parameter_references(
    raw: str | None,
    key: str,
    replacement: str,
    param_type: str | None = "string",
):
    """恢复 JSON 中的参数引用，完整引用按参数类型还原，嵌入文本仍保留字符串。"""
    if raw is None:
        return raw, False
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw, False

    tokens = set(_parameter_reference_tokens(key))
    typed_replacement = _parameter_value_for_json(replacement, param_type)

    def replace(value):
        if isinstance(value, str):
            if value in tokens:
                return typed_replacement, True
            next_value = _replace_parameter_reference_tokens(value, key, replacement)
            return next_value, next_value != value
        if isinstance(value, list):
            changed = False
            next_values = []
            for item in value:
                next_item, item_changed = replace(item)
                next_values.append(next_item)
                changed = changed or item_changed
            return next_values, changed
        if isinstance(value, dict):
            changed = False
            next_values = {}
            for item_key, item_value in value.items():
                next_item, item_changed = replace(item_value)
                next_values[item_key] = next_item
                changed = changed or item_changed
            return next_values, changed
        return value, False

    restored, changed = replace(value)
    if not changed:
        return raw, False
    return json.dumps(restored, ensure_ascii=False, indent=2), True


def _deparameterize_text(value: str | None, key: str, replacement: str, param_type: str | None = "string"):
    if value is None:
        return value, False
    if param_type not in {None, "string", "date", "datetime", "random", "expression"}:
        restored, changed = _replace_json_parameter_references(value, key, replacement, param_type)
        if changed:
            return restored, True
    result = _replace_parameter_reference_tokens(value, key, replacement)
    return result, result != value


def _candidate_origin(source: str | None) -> tuple[str, str]:
    source_text = (source or "").strip()
    if source_text.lower() == "curl":
        return "curl", "cURL导入"
    if source_text:
        return "file", "文件导入"
    return "manual", "手动创建"


def _apply_candidate_origin(candidates: list[dict], source: str | None) -> list[dict]:
    origin_type, origin_label = _candidate_origin(source)
    for item in candidates:
        item["origin_type"] = origin_type
        item["origin_label"] = origin_label
        item["origin_source"] = source or ""
    return candidates


async def _find_parameter_item_references(db: AsyncSession, project_id: int, key: str) -> list[dict]:
    from models.models import Interface, InterfaceCollection, TestCase

    refs: list[dict] = []
    iface_result = await db.execute(
        select(Interface).join(InterfaceCollection).where(
            InterfaceCollection.project_id == project_id,
            Interface.is_deleted == False
        )
    )
    for iface in iface_result.scalars().all():
        refs.extend(_find_references_in_record("interface", iface, key))

    tc_result = await db.execute(
        select(TestCase).options(joinedload(TestCase.interface)).where(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False
        )
    )
    for tc in tc_result.scalars().all():
        refs.extend(_find_references_in_record("testcase", tc, key))
    return refs


async def _deparameterize_parameter_references_bulk(
    db: AsyncSession,
    project_id: int,
    replacements: dict[str, tuple[str, str | None]],
) -> int:
    """一次扫描项目数据，恢复多个参数引用，供全部删除等批量操作使用。"""
    from models.models import Interface, InterfaceCollection, TestCase

    if not replacements:
        return 0

    replaced_count = 0
    iface_result = await db.execute(
        select(Interface).join(InterfaceCollection).where(
            InterfaceCollection.project_id == project_id,
            Interface.is_deleted == False
        )
    )
    for iface in iface_result.scalars().all():
        for attr in ("headers", "query_params", "path_params"):
            values = getattr(iface, attr, []) or []
            for key, (replacement, _param_type) in replacements.items():
                values, changed = _deparameterize_list_values(values, key, replacement)
                if changed:
                    setattr(iface, attr, values)
                    replaced_count += 1
        body_content = getattr(iface, "body_content", None)
        for key, (replacement, param_type) in replacements.items():
            body_content, changed = _deparameterize_text(body_content, key, replacement, param_type)
            if changed:
                setattr(iface, "body_content", body_content)
                replaced_count += 1

    tc_result = await db.execute(
        select(TestCase).options(joinedload(TestCase.interface)).where(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False
        )
    )
    for tc in tc_result.scalars().all():
        overrides = dict(tc.param_overrides or {})
        changed_any = False
        for attr in ("headers", "query_params", "path_params"):
            values = overrides.get(attr, []) or []
            for key, (replacement, _param_type) in replacements.items():
                values, changed = _deparameterize_list_values(values, key, replacement)
                if changed:
                    overrides[attr] = values
                    changed_any = True
                    replaced_count += 1
        body_content = overrides.get("body_content")
        for key, (replacement, param_type) in replacements.items():
            body_content, changed = _deparameterize_text(body_content, key, replacement, param_type)
            if changed:
                overrides["body_content"] = body_content
                changed_any = True
                replaced_count += 1
        if changed_any:
            tc.param_overrides = overrides

    return replaced_count


async def _deparameterize_parameter_references(
    db: AsyncSession,
    project_id: int,
    key: str,
    replacement: str,
    param_type: str | None = "string",
) -> int:
    return await _deparameterize_parameter_references_bulk(
        db, project_id, {key: (replacement, param_type)}
    )
