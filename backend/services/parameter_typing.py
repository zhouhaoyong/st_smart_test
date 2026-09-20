import json
import re
from typing import Any


PARAM_TYPES = {"string", "int", "float", "bool", "list", "object", "date", "datetime", "random", "expression"}
IGNORED_PARAM_HEADER_NAMES = {
    "accept",
    "accept-encoding",
    "accept-language",
    "authorization",
    "cache-control",
    "connection",
    "content-length",
    "content-type",
    "cookie",
    "host",
    "origin",
    "pragma",
    "referer",
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
    "user-agent",
    "x-requested-with",
}


def normalize_schema_type(schema: dict | None) -> str:
    """Map OpenAPI/JSON Schema types to parameter set types."""
    if not isinstance(schema, dict):
        return "string"
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((t for t in schema_type if t != "null"), schema_type[0] if schema_type else None)
    if schema_type == "integer":
        return "int"
    if schema_type == "number":
        return "float"
    if schema_type == "boolean":
        return "bool"
    if schema_type == "array":
        return "list"
    if schema_type == "object":
        return "object"
    return "string"


def schema_type_map(schema: dict | None, prefix: str = "") -> dict[str, str]:
    if not isinstance(schema, dict):
        return {}
    result = {}
    schema_type = normalize_schema_type(schema)
    if prefix:
        result[prefix] = schema_type
    if "$ref" in schema:
        return result
    if "allOf" in schema:
        for part in schema.get("allOf") or []:
            result.update(schema_type_map(part, prefix))
    props = schema.get("properties") or {}
    for key, child in props.items():
        child_path = f"{prefix}.{key}" if prefix else key
        result.update(schema_type_map(child, child_path))
    if schema.get("items") and prefix:
        result[prefix] = "list"
        result.update(schema_type_map(schema.get("items"), f"{prefix}.0"))
    return result


def infer_param_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"

    text = "" if value is None else str(value).strip()
    if re.fullmatch(r"[+-]?\d+", text):
        return "int"
    if re.fullmatch(r"[+-]?(?:\d+\.\d+|\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?", text) or re.fullmatch(r"[+-]?\d+[eE][+-]?\d+", text):
        return "float"
    if text.lower() in {"true", "false"}:
        return "bool"
    try:
        parsed = json.loads(text)
    except Exception:
        return "string"
    if isinstance(parsed, list):
        return "list"
    if isinstance(parsed, dict):
        return "object"
    return "string"


def validate_parameter_value(param_type: str, value: Any) -> str | None:
    param_type = param_type or "string"
    if param_type not in PARAM_TYPES:
        return "不支持的参数类型"
    if param_type in {"string", "date", "datetime", "random", "expression"}:
        return None

    text = "" if value is None else str(value).strip()
    if param_type == "int":
        return None if re.fullmatch(r"[+-]?\d+", text) else "请输入合法的 int 类型"
    if param_type == "float":
        try:
            float(text)
        except Exception:
            return "请输入合法的 float 类型"
        return None
    if param_type == "bool":
        return None if text.lower() in {"true", "false"} else "请输入合法的 bool 类型"
    try:
        parsed = json.loads(text)
    except Exception:
        return f"请输入合法的 {param_type} 类型"
    if param_type == "list":
        return None if isinstance(parsed, list) else "请输入合法的 list 类型"
    if param_type == "object":
        return None if isinstance(parsed, dict) else "请输入合法的 object 类型"
    return None


CANDIDATE_STATUS_NORMAL = "normal"
CANDIDATE_STATUS_EMPTY = "empty"
CANDIDATE_STATUS_INVALID = "invalid"
CANDIDATE_STATUS_TYPE_CONFLICT = "type_conflict"
CANDIDATE_STATUS_NEEDS_CONFIRMATION = "needs_confirmation"

CANDIDATE_STATUS_LABELS = {
    CANDIDATE_STATUS_NORMAL: "正常候选",
    CANDIDATE_STATUS_EMPTY: "待补充",
    CANDIDATE_STATUS_INVALID: "非法值",
    CANDIDATE_STATUS_TYPE_CONFLICT: "类型冲突",
    CANDIDATE_STATUS_NEEDS_CONFIRMATION: "需要确认",
}


def _stringify_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def classify_parameter_candidate(value: Any, param_type: str) -> str:
    """Classify a value against the type that governs the parameter contract."""
    text = _stringify_value(value).strip()
    if not text:
        return CANDIDATE_STATUS_EMPTY
    return CANDIDATE_STATUS_INVALID if validate_parameter_value(param_type, text) else CANDIDATE_STATUS_NORMAL


def candidate_status_label(status: str) -> str:
    return CANDIDATE_STATUS_LABELS.get(status, "需要确认")


def _candidate_locator(candidate: dict) -> tuple[str, str]:
    field_path = str(candidate.get("field_path") or "")
    if field_path.startswith("param_overrides."):
        field_path = field_path[len("param_overrides."):]
    for prefix in ("headers.", "query_params.", "path_params."):
        if field_path.startswith(prefix):
            return prefix[:-1], str(candidate.get("key") or "").strip()
    if field_path.startswith("body_content_json."):
        return "body", field_path[len("body_content_json."):]
    return "unknown", str(candidate.get("key") or "").strip()


def _type_source_priority(type_source: str | None) -> int:
    return {"schema": 4, "manual": 3, "inferred": 2, "default": 1}.get(type_source or "", 0)


def resolve_parameter_contract(candidate: dict, interface_candidates: list[dict] | None) -> dict | None:
    """Resolve a testcase candidate's type from its linked interface definition."""
    locator = _candidate_locator(candidate)
    matches = [
        item for item in interface_candidates or []
        if _candidate_locator(item) == locator and item.get("type")
    ]
    if not matches and locator[0] == "body":
        leaf_key = str(candidate.get("key") or "").strip()
        body_matches = [
            item for item in interface_candidates or []
            if _candidate_locator(item)[0] == "body"
            and str(item.get("key") or "").strip() == leaf_key
            and item.get("type")
        ]
        if len(body_matches) == 1:
            matches = body_matches
    if not matches:
        return None

    type_by_name = {}
    for item in matches:
        type_by_name.setdefault(str(item["type"]), []).append(item)
    if len(type_by_name) > 1:
        return {
            "type": "",
            "type_source": "conflict",
            "conflict": True,
            "types": sorted(type_by_name),
        }

    selected = max(matches, key=lambda item: _type_source_priority(item.get("type_source")))
    return {
        "type": str(selected["type"]),
        "type_source": selected.get("type_source") or "manual",
        "conflict": False,
    }


def aggregate_parameter_candidates(candidates: list[dict]) -> list[dict]:
    """Merge all observations of one Key while retaining source-level evidence."""
    grouped: dict[str, dict] = {}
    for item in candidates or []:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        candidate = dict(item)
        candidate["value"] = _stringify_value(candidate.get("value"))
        status = candidate.get("candidate_status") or classify_parameter_candidate(
            candidate["value"], candidate.get("type") or "string"
        )
        candidate["candidate_status"] = status
        group = grouped.setdefault(key, {
            "key": key,
            "display_name": candidate.get("display_name") or key,
            "value": "",
            "type": "",
            "type_source": "",
            "description": candidate.get("description") or "",
            "hit_count": 0,
            "sources": [],
            "origin_labels": [],
            "_items": [],
        })
        group["hit_count"] += 1
        group["_items"].append(candidate)
        group["sources"].append({
            "source_type": candidate.get("source_type", ""),
            "source_id": candidate.get("source_id"),
            "source_name": candidate.get("source_name", ""),
            "field_path": candidate.get("field_path", ""),
            "match_type": candidate.get("match_type", ""),
            "origin_type": candidate.get("origin_type", "manual"),
            "origin_label": candidate.get("origin_label", "手动创建"),
            "origin_source": candidate.get("origin_source", ""),
            "value": candidate["value"],
            "type": candidate.get("type") or "",
            "type_source": candidate.get("type_source") or "default",
            "candidate_status": status,
            "candidate_status_label": candidate_status_label(status),
        })
        origin_label = candidate.get("origin_label")
        if origin_label and origin_label not in group["origin_labels"]:
            group["origin_labels"].append(origin_label)

    results = []
    for group in grouped.values():
        observations = group.pop("_items")
        contract_types = {str(item["contract_type"]) for item in observations if item.get("contract_type")}
        fallback_types = {
            str(item.get("type")) for item in observations
            if not item.get("contract_type") and item.get("type")
        }
        type_conflict = len(contract_types) > 1 or (not contract_types and len(fallback_types) > 1)
        if type_conflict:
            group["candidate_status"] = CANDIDATE_STATUS_TYPE_CONFLICT
            group["candidate_status_label"] = candidate_status_label(CANDIDATE_STATUS_TYPE_CONFLICT)
            group["type"] = ""
            group["type_source"] = "conflict"
            group["value"] = ""
            results.append(group)
            continue

        effective_type = next(iter(contract_types or fallback_types), "")
        group["type"] = effective_type
        type_items = [item for item in observations if str(item.get("type") or "") == effective_type]
        selected_type_item = max(type_items, key=lambda item: _type_source_priority(item.get("type_source")), default=None)
        group["type_source"] = (selected_type_item or {}).get("type_source") or "default"

        normal_items = [
            item for item in observations
            if classify_parameter_candidate(item.get("value"), effective_type or item.get("type") or "string") == CANDIDATE_STATUS_NORMAL
        ]
        normal_items.sort(key=lambda item: (0 if item.get("source_type") == "interface" else 1))
        if normal_items:
            selected = normal_items[0]
            group["value"] = _stringify_value(selected.get("value"))
            group["candidate_status"] = CANDIDATE_STATUS_NORMAL
        elif any(item.get("candidate_status") == CANDIDATE_STATUS_INVALID for item in observations):
            selected = next(item for item in observations if item.get("candidate_status") == CANDIDATE_STATUS_INVALID)
            group["value"] = _stringify_value(selected.get("value"))
            group["candidate_status"] = CANDIDATE_STATUS_INVALID
        elif any(item.get("candidate_status") == CANDIDATE_STATUS_EMPTY for item in observations):
            group["candidate_status"] = CANDIDATE_STATUS_EMPTY
        else:
            group["candidate_status"] = CANDIDATE_STATUS_NEEDS_CONFIRMATION
        group["candidate_status_label"] = candidate_status_label(group["candidate_status"])
        results.append(group)

    return sorted(results, key=lambda item: (-item["hit_count"], item["key"]))


def walk_body_candidates(body_content: str | None, schema_types: dict[str, str] | None = None, source: str = "interface") -> list[dict]:
    if not body_content:
        return []
    try:
        body = json.loads(body_content)
    except Exception:
        return []

    schema_types = schema_types or {}
    candidates = []

    def walk(value: Any, path: list[str]):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, [*path, key])
            return
        if isinstance(value, list):
            key_path = ".".join(path)
            leaf_key = path[-1] if path else "items"
            candidates.append({
                "key": leaf_key,
                "display_name": leaf_key,
                "value": _stringify_value(value),
                "type": schema_types.get(key_path) or "list",
                "type_source": "schema" if key_path in schema_types else "inferred",
                "source": source,
                "field_path": f"body_content_json.{key_path}",
                "match_type": f"请求体字段 {key_path}",
            })
            return
        key_path = ".".join(path)
        leaf_key = path[-1] if path else "value"
        candidates.append({
            "key": leaf_key,
            "display_name": leaf_key,
            "value": _stringify_value(value),
            "type": schema_types.get(key_path) or infer_param_type(value),
            "type_source": "schema" if key_path in schema_types else "inferred",
            "source": source,
            "field_path": f"body_content_json.{key_path}",
            "match_type": f"请求体字段 {key_path}",
        })

    walk(body, [])
    return candidates


def _candidate_from_pair(item: dict, field_path: str, match_type: str, source_type: str, source_id: int, source_name: str) -> dict | None:
    key = str(item.get("key") or "").strip()
    if not key:
        return None
    value = item.get("value", "")
    param_type = item.get("type") or infer_param_type(value)
    return {
        "key": key,
        "display_name": key,
        "value": _stringify_value(value),
        "type": param_type,
        "type_source": item.get("type_source") or ("inferred" if value not in ("", None) else "default"),
        "description": item.get("description") or "",
        "source_type": source_type,
        "source_id": source_id,
        "source_name": source_name,
        "field_path": field_path,
        "match_type": match_type,
    }


def _is_ignored_param_header(item: dict) -> bool:
    key = str(item.get("key") or "").strip().lower()
    return key in IGNORED_PARAM_HEADER_NAMES


def collect_param_candidates(
    source_type: str,
    source_id: int,
    source_name: str,
    headers: list | None = None,
    query_params: list | None = None,
    path_params: list | None = None,
    body_content: str | None = None,
    body_schema_types: dict[str, str] | None = None,
    include_headers: bool = False,
) -> list[dict]:
    candidates = []
    if not include_headers:
        headers = []
    for idx, item in enumerate(headers or []):
        if isinstance(item, dict):
            if _is_ignored_param_header(item):
                continue
            candidate = _candidate_from_pair(item, f"headers.{idx}.value", f"请求头 {item.get('key', '')}", source_type, source_id, source_name)
            if candidate:
                candidates.append(candidate)
    for idx, item in enumerate(query_params or []):
        if isinstance(item, dict):
            candidate = _candidate_from_pair(item, f"query_params.{idx}.value", f"查询参数 {item.get('key', '')}", source_type, source_id, source_name)
            if candidate:
                candidates.append(candidate)
    for idx, item in enumerate(path_params or []):
        if isinstance(item, dict):
            candidate = _candidate_from_pair(item, f"path_params.{idx}.value", f"路径参数 {item.get('key', '')}", source_type, source_id, source_name)
            if candidate:
                candidates.append(candidate)

    for item in walk_body_candidates(body_content, body_schema_types, source_type):
        item.update({
            "source_type": source_type,
            "source_id": source_id,
            "source_name": source_name,
            "description": item.get("description") or "",
        })
        candidates.append(item)
    return candidates
