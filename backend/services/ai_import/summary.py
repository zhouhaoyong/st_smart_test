"""接口列表 AI 生成用例的数据加工与运行契约归一。

职责边界：
- 只做“数据加工”，不碰数据库、不调 AI、不管权限；
- 生成“接口明细”作为 AI 用例生成输入，脱敏；
- 把 AI 用例生成结果容错归一，单条坏数据不影响整体；
- 用例输出严格映射到运行引擎认识的 param_overrides 契约 + 顶层 assertions，
  避免“能保存、不能运行”。

关键契约（与 backend/api/v1/endpoints/executor.py 的 /run-case 一致）：
- 运行时请求内容几乎全部读 test_cases.param_overrides，固定键名：
  method / url / headers / query_params / path_params / body_type /
  body_content / pre_script / post_script / service_key。
- 前置/后置脚本必须写进 param_overrides.pre_script / post_script，
  顶层 script 运行时不读。
- 断言写顶层 assertions，结构 {type, expression, operator, expected, enabled}；
  基础断言断言响应体业务码：$.code eq "200"，而非 HTTP 状态码。
"""
from __future__ import annotations

import json
import re
from typing import Any

from services.ai_import.generation import resolve_operation_type

# ---- 运行契约常量：改这里等于改运行行为，务必与 executor.py 对齐 ----

PARAM_OVERRIDE_KEYS = (
    "method",
    "url",
    "headers",
    "query_params",
    "path_params",
    "body_type",
    "body_content",
    "pre_script",
    "post_script",
    "service_key",
)

DEFAULT_ASSERTION = {
    "type": "jsonpath",
    "expression": "$.code",
    "operator": "eq",
    "expected": "200",
    "enabled": True,
}


def assertion_for_case_type(case_type: Any) -> list[dict]:
    """为新用例挂统一的业务码判定标准，具体断言由用户继续编辑。"""
    return [dict(DEFAULT_ASSERTION)]

# 请求头中需要脱敏的敏感键（小写比较）。
_SENSITIVE_HEADER_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "apikey",
    "x-auth-token",
    "x-token",
    "token",
    "access-token",
    "x-access-token",
}

# 参数 / 请求体字段名中命中这些子串则脱敏（小写比较）。
_SENSITIVE_NAME_HINTS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "access_key",
    "accesskey",
    "private_key",
    "credential",
    "authorization",
)

_REDACTED = "<脱敏>"


# ========== 基础工具 ==========

def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def _fallback_case_name_prefix(iface: dict) -> str:
    method = _as_str(iface.get("method")).strip().upper()
    return {
        "GET": "查询接口",
        "HEAD": "查询接口",
        "OPTIONS": "查询接口",
        "POST": "创建接口",
        "PUT": "更新接口",
        "PATCH": "更新接口",
        "DELETE": "删除接口",
    }.get(method, "接口调用")


def normalize_case_name_prefix(iface: dict, candidate: Any = "") -> str:
    """返回用于测试用例命名的中文功能前缀，禁止把英文接口名直接带入名称。"""
    candidate_name = re.sub(r"\s+", " ", _as_str(candidate)).strip(" _-")
    if _contains_chinese(candidate_name):
        return candidate_name[:60]

    source_name = re.sub(r"\s+", " ", _as_str(iface.get("name"))).strip(" _-")
    if _contains_chinese(source_name):
        return source_name[:60]

    return _fallback_case_name_prefix(iface)


def _case_name_suffix(case: dict, sequence: int) -> str:
    suffix = _as_str(case.get("name_suffix") or case.get("name")).strip(" _-")
    if not suffix:
        return f"异常用例{sequence}"

    # 兼容旧格式的“英文接口名_场景”名称，新的协议优先使用 name_suffix。
    if not case.get("name_suffix") and "_" in suffix:
        prefix, remainder = suffix.split("_", 1)
        if prefix and remainder and not _contains_chinese(prefix) and _contains_chinese(remainder):
            suffix = remainder.strip(" _-")
    return suffix[:60] or f"异常用例{sequence}"


def _compose_case_name(prefix: str, suffix: str) -> str:
    prefix = _as_str(prefix).strip(" _-") or "接口调用"
    suffix = _as_str(suffix).strip(" _-") or "异常用例"
    return f"{prefix}_{suffix}"[:100]


def _is_sensitive_name(name: str) -> bool:
    low = (name or "").lower()
    return any(hint in low for hint in _SENSITIVE_NAME_HINTS)


def _redact_kv_list(items: Any) -> list[dict]:
    """脱敏参数值，同时保留生成测试值需要的类型和约束信息。"""
    result = []
    for item in _as_list(items):
        d = _as_dict(item)
        key = _as_str(d.get("key"))
        entry = {"key": key, "value": d.get("value")}
        for name in (
            "description", "type", "schema_type", "type_source", "required", "default", "example", "enum",
            "format", "pattern", "minimum", "maximum", "exclusive_minimum", "exclusive_maximum",
            "min_length", "max_length", "min_items", "max_items",
        ):
            if name in d:
                entry[name] = d[name]
        low = key.lower()
        if low in _SENSITIVE_HEADER_KEYS or _is_sensitive_name(key):
            entry["value"] = _REDACTED
            for name in ("default", "example", "enum"):
                if name in entry:
                    entry[name] = _REDACTED
        result.append(entry)
    return result


def _redact_body_content(body_type: Any, body_content: Any) -> Any:
    """脱敏请求体：JSON 体递归打码敏感字段名，其他类型原样返回。"""
    if body_content in (None, ""):
        return body_content
    if not isinstance(body_content, str):
        return body_content
    text = body_content
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return text  # 非 JSON 文本原样返回（无法安全定位敏感字段）
    return json.dumps(_redact_json(parsed), ensure_ascii=False, indent=2)


def _redact_json(node: Any) -> Any:
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if _is_sensitive_name(_as_str(k)):
                out[k] = _REDACTED
            else:
                out[k] = _redact_json(v)
        return out
    if isinstance(node, list):
        return [_redact_json(v) for v in node]
    return node

# ========== 接口明细（AI 用例生成输入，脱敏）==========

def detail_for_generate(iface: dict, plan: dict | None = None) -> dict:
    """生成阶段发送接口请求结构 + 本接口的覆盖计划，敏感内容已脱敏。

    - 只出可直接运行的字面值用例，不做参数化；认证由运行环境注入，
      故不下发项目变量名清单；
    - 不下发响应示例：断言由程序统一挂，模型用不上响应结构，
      下发只会白白占用上下文并拖慢生成；
    - plan 指明这个接口该往哪些方向补、最多补几条，由生成策略算出。
    """
    detail = {
        "temp_id": iface.get("temp_id"),
        "name": iface.get("name"),
        "method": iface.get("method"),
        "url": iface.get("url"),
        "description": (iface.get("description") or "")[:500],
        "query_params": _redact_kv_list(iface.get("query_params")),
        "path_params": _redact_kv_list(iface.get("path_params")),
        "headers": _redact_kv_list(iface.get("headers")),
        "body_type": iface.get("body_type"),
        "body_content": _redact_body_content(iface.get("body_type"), iface.get("body_content")),
        "body_schema_types": iface.get("body_schema_types") or {},
        "body_required_fields": iface.get("body_required_fields") or [],
    }
    p = _as_dict(plan)
    if p:
        detail["operation_type"] = p.get("operation_type")
        detail["case_types"] = p.get("case_types") or []
        detail["max_cases"] = p.get("max_cases") or 0
        detail["focus"] = p.get("focus") or {}
    return detail


# ========== AI 用例生成结果归一 → param_overrides 契约 ==========

def build_param_overrides(iface: dict, ai_overrides: Any) -> dict:
    """按运行契约构造 param_overrides，缺省回退接口默认，脚本落到脚本键。"""
    ov = _as_dict(ai_overrides)

    method = _as_str(ov.get("method")).upper() or iface.get("method") or "GET"
    url = _as_str(ov.get("url")) or _as_str(iface.get("url"))

    headers = _coerce_kv(ov.get("headers")) if ov.get("headers") is not None else _plain_kv(iface.get("headers"))
    query_params = _coerce_kv(ov.get("query_params")) if ov.get("query_params") is not None else _plain_kv(iface.get("query_params"))
    path_params = _coerce_kv(ov.get("path_params")) if ov.get("path_params") is not None else _plain_kv(iface.get("path_params"))

    body_type = ov.get("body_type") if ov.get("body_type") is not None else iface.get("body_type")
    body_content = ov.get("body_content") if ov.get("body_content") is not None else iface.get("body_content")

    # 脚本必须落到 param_overrides.pre_script / post_script，顶层 script 运行时不读。
    pre_script = ov.get("pre_script")
    if pre_script is None:
        pre_script = iface.get("pre_script")
    post_script = ov.get("post_script")
    if post_script is None:
        post_script = iface.get("post_script")

    overrides = {
        "method": method,
        "url": url,
        "headers": headers,
        "query_params": query_params,
        "path_params": path_params,
        "body_type": body_type,
        "body_content": body_content,
        "body_schema_types": _as_dict(iface.get("body_schema_types")),
        "pre_script": pre_script,
        "post_script": post_script,
    }

    # 服务不从接口继承到用例：接口的服务在运行时兜底，用例只在用户显式指定时才记。
    # 写一个空的 service_key 会被单条运行误判成“明确不使用服务”，也会在用户回到
    # 上一步改接口服务后变成过期值，故没有值就整个键不写。
    service_key = _as_str(ov.get("service_key")).strip()
    if service_key:
        overrides["service_key"] = service_key
    return overrides


def _plain_kv(items: Any) -> list[dict]:
    """接口默认参数列表 → 运行需要的 [{key,value}]（丢弃 type 等描述字段）。"""
    out = []
    for item in _as_list(items):
        d = _as_dict(item)
        out.append({"key": _as_str(d.get("key")), "value": d.get("value") if d.get("value") is not None else ""})
    return out


def _coerce_kv(value: Any) -> list[dict]:
    """AI 输出的参数覆盖统一成 [{key,value}]：兼容 dict 与 list 两种写法。"""
    if isinstance(value, dict):
        return [{"key": _as_str(k), "value": v if v is not None else ""} for k, v in value.items()]
    out = []
    for item in _as_list(value):
        d = _as_dict(item)
        if "key" in d:
            out.append({"key": _as_str(d.get("key")), "value": d.get("value") if d.get("value") is not None else ""})
    return out


def case_request_signature(iface: dict, overrides: dict | None) -> str:
    """按实际请求内容生成签名，合并同一测试等价类而不是只比较用例名称。"""
    ov = _as_dict(overrides)
    params = {}
    for target, key in (("query", "query_params"), ("path", "path_params"), ("header", "headers")):
        declared = {
            _as_str(_as_dict(item).get("key") or _as_dict(item).get("name")): _as_str(
                _as_dict(item).get("type") or _as_dict(item).get("schema_type")
            ).lower()
            for item in _as_list(iface.get(key))
        }
        values = []
        for item in _coerce_kv(ov.get(key)):
            field, value = _as_str(item.get("key")), item.get("value")
            kind = declared.get(field, "")
            if isinstance(value, str) and not value.strip():
                value = ["empty"]
            elif kind in {"int", "integer", "long", "float", "number", "double", "bool", "boolean"}:
                try:
                    if kind in {"int", "integer", "long"}:
                        if isinstance(value, float) and not value.is_integer():
                            raise ValueError
                        value = int(value)
                    elif kind in {"bool", "boolean"} and str(value).lower() not in {"true", "false"}:
                        raise ValueError
                    elif kind in {"bool", "boolean"}:
                        value = str(value).lower()
                    else:
                        value = float(value)
                except (TypeError, ValueError):
                    value = ["invalid", kind]
            values.append((field, value))
        params[target] = sorted(values, key=lambda item: item[0])
    body = ov.get("body_content")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (TypeError, ValueError):
            pass
    payload = {
        "method": _as_str(ov.get("method") or iface.get("method")).upper(),
        "url": _as_str(ov.get("url") or iface.get("url")),
        "params": params,
        "body_type": ov.get("body_type"),
        "body": body,
        "pre_script": ov.get("pre_script"),
        "post_script": ov.get("post_script"),
        "service_key": ov.get("service_key"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


VALID_CASE_TYPES = ("main", "reverse", "abnormal")

# AI 增量用例只能改动这几个位置，其余键名一律忽略。
_CHANGE_TARGETS = {
    "query": "query_params",
    "query_params": "query_params",
    "path": "path_params",
    "path_params": "path_params",
    "header": "headers",
    "headers": "headers",
    "body": "body",
}


def _normalize_case_type(value: Any) -> str:
    t = _as_str(value).lower()
    return t if t in VALID_CASE_TYPES else "reverse"


def _apply_kv_change(items: list[dict], field: str, action: str, value: Any) -> bool:
    """在 [{key,value}] 列表上执行一次增删改，返回是否真的改动了请求内容。"""
    if action == "remove":
        before = len(items)
        items[:] = [i for i in items if _as_str(i.get("key")) != field]
        return len(items) != before
    for item in items:
        if _as_str(item.get("key")) == field:
            item["value"] = value
            return True
    items.append({"key": field, "value": value})
    return True


def _apply_body_change(overrides: dict, field: str, action: str, value: Any) -> bool:
    """在 JSON 请求体上执行一次增删改；非 JSON 请求体无法安全定位字段，直接放弃。"""
    raw = overrides.get("body_content")
    if not raw and overrides.get("body_type") in {"json", "application/json"}:
        parsed = {}
    else:
        if not isinstance(raw, str) or not raw.strip():
            return False
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return False
    if not isinstance(parsed, dict):
        return False
    segments = [part for part in _as_str(field).removeprefix("$.").split(".") if part]
    if not segments:
        return False
    parent = parsed
    for segment in segments[:-1]:
        if not isinstance(parent, dict):
            return False
        if segment not in parent:
            if action == "remove":
                return False
            parent[segment] = {}
        parent = parent[segment]
    if not isinstance(parent, dict):
        return False
    field = segments[-1]
    if action == "remove":
        if field not in parent:
            return False
        parent.pop(field)
    else:
        parent[field] = value
    overrides["body_content"] = json.dumps(parsed, ensure_ascii=False, indent=2)
    return True


def apply_case_changes(
    base_overrides: dict,
    changes: Any,
    allowed_fields: dict[str, set[str]] | None = None,
) -> tuple[dict, list[str]]:
    """把 AI 给出的原子改动叠加到基础请求上，返回新的请求内容与提示。

    改动结构：[{target: query/path/header/body, field: 字段名, action: set/remove, value: 值}]。
    只允许改这几个位置，无法落地的改动跳过并记提示，不让单条坏数据毁掉整条用例。
    """
    overrides = json.loads(json.dumps(base_overrides, ensure_ascii=False))
    warnings: list[str] = []
    applied = 0
    for raw in _as_list(changes):
        d = _as_dict(raw)
        target = _CHANGE_TARGETS.get(_as_str(d.get("target")).lower())
        field = _as_str(d.get("field")).strip()
        action = "remove" if _as_str(d.get("action")).lower() == "remove" else "set"
        if not target or not field:
            continue
        if allowed_fields is not None and field not in allowed_fields.get(target, set()):
            warnings.append(f"参数「{field}」不在接口定义中，已忽略改动")
            continue
        value = d.get("value")
        if target == "body":
            ok = _apply_body_change(overrides, field, action, value)
            if not ok:
                warnings.append(f"请求体字段「{field}」的改动未能应用（请求体不是可解析的 JSON 或字段不存在）")
                continue
        else:
            items = overrides.get(target)
            if not isinstance(items, list):
                items = []
                overrides[target] = items
            if not _apply_kv_change(items, field, action, value):
                warnings.append(f"参数「{field}」的改动未能应用")
                continue
        applied += 1
    if not applied:
        warnings.append("模型未给出有效的参数改动，本条用例与基础请求内容相同，请人工确认")
    return overrides, warnings


def _allowed_change_fields(iface: dict) -> dict[str, set[str]]:
    fields = {
        target: {
            _as_str(_as_dict(item).get("key") or _as_dict(item).get("name")).strip()
            for item in _as_list(iface.get(source))
            if _as_str(_as_dict(item).get("key") or _as_dict(item).get("name")).strip()
        }
        for target, source in (
            ("query_params", "query_params"),
            ("path_params", "path_params"),
            ("headers", "headers"),
        )
    }
    fields["body"] = {
        _as_str(key).removeprefix("$.")
        for key in _as_dict(iface.get("body_schema_types"))
    }
    fields["body"].update(
        _as_str(field).removeprefix("$.")
        for field in _as_list(iface.get("body_required_fields"))
        if _as_str(field).strip()
    )
    body = iface.get("body_content")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (TypeError, ValueError):
            body = {}
    if isinstance(body, dict):
        fields["body"].update(str(field) for field in body)
    return fields


def _missing_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _missing_only_changes(base_overrides: dict, changes: Any) -> list[dict]:
    """主流程只接受对当前空值的补充，不覆盖接口已有值。"""
    result = []
    for raw in _as_list(changes):
        d = _as_dict(raw)
        target = _CHANGE_TARGETS.get(_as_str(d.get("target")).lower())
        field = _as_str(d.get("field")).strip()
        action = _as_str(d.get("action")).lower()
        if not target or not field or action == "remove":
            continue
        if target == "body":
            current = base_overrides.get("body_content")
            try:
                current = json.loads(current) if isinstance(current, str) else current
            except (TypeError, ValueError):
                current = {}
            value = current
            for segment in _as_str(field).removeprefix("$.").split("."):
                if not isinstance(value, dict) or segment not in value:
                    value = None
                    break
                value = value[segment]
        else:
            values = {item.get("key"): item.get("value") for item in _coerce_kv(base_overrides.get(target))}
            value = values.get(field)
        if _missing_value(value):
            result.append(d)
    return result


def _apply_main_changes(iface: dict, case: dict, changes: Any, plan: dict) -> dict:
    operation = _as_dict(plan).get("operation_type") or resolve_operation_type(iface)
    method = _as_str(iface.get("method")).upper()
    if operation != "read" or method not in {"GET", "HEAD", "OPTIONS"}:
        return case
    filtered = _missing_only_changes(case.get("param_overrides") or {}, changes)
    if not filtered:
        return case
    overrides, warnings = apply_case_changes(
        case["param_overrides"],
        filtered,
        _allowed_change_fields(iface),
    )
    if overrides == case["param_overrides"]:
        return case
    return build_system_generated_case(iface, overrides, warnings)[0]


def _generation_payload(value: Any) -> tuple[list, list, str]:
    if isinstance(value, dict):
        return (
            _as_list(value.get("cases")),
            _as_list(value.get("base_changes")),
            _as_str(value.get("case_name_prefix")),
        )
    return _as_list(value), [], ""


def cases_by_temp_id(ai_output: Any) -> dict[str, list]:
    """把一批接口的 AI 用例输出按 temp_id 拆分，容错丢弃无效条目。"""
    out: dict[str, list] = {}
    for item in _as_list(_as_dict(ai_output).get("interfaces")):
        d = _as_dict(item)
        temp_id = _as_str(d.get("temp_id"))
        if not temp_id:
            continue
        out[temp_id] = _as_list(d.get("cases"))
    return out


def merge_generated_cases(iface: dict, ai_cases: Any, plan: dict | None = None) -> list[dict]:
    """组装单个接口的最终用例：系统生成的基础用例 + AI 补充的增量用例。

    - 基础用例那条永远由系统按接口定义生成，参数忠于当前导入数据，不消耗额度；
    - AI 增量只描述“改了哪个参数”，由程序叠加到基础请求上，超出上限的部分截断；
    - 判定标准一律程序挂：所有用例统一使用业务码 200，AI 输出的断言不采信。
    """
    p = _as_dict(plan)
    allowed = tuple(t for t in (p.get("case_types") or ("reverse",)) if t in VALID_CASE_TYPES and t != "main")
    max_cases = max(0, int(p.get("max_cases") or 0))

    ai_case_items, base_changes, candidate_prefix = _generation_payload(ai_cases)
    case_name_prefix = normalize_case_name_prefix(iface, candidate_prefix)
    cases = build_system_generated_case(iface)
    cases[0] = _apply_main_changes(iface, cases[0], base_changes, p)
    cases[0]["name"] = _compose_case_name(case_name_prefix, "基础用例")
    base_overrides = cases[0]["param_overrides"]
    if not allowed or not max_cases:
        return cases

    seq = 0
    seen_signatures = {case_request_signature(iface, base_overrides)}
    for raw in ai_case_items:
        if seq >= max_cases:
            break
        d = _as_dict(raw)
        case_type = _normalize_case_type(d.get("case_type"))
        if case_type not in allowed:
            continue
        # 优先采信原子改动；模型若仍给整份请求覆盖，退化为按组覆盖，避免整条丢弃。
        if d.get("changes") is not None or d.get("param_overrides") is None:
            overrides, change_warnings = apply_case_changes(
                base_overrides,
                d.get("changes"),
                _allowed_change_fields(iface),
            )
        else:
            overrides, change_warnings = build_param_overrides(iface, d.get("param_overrides")), []
        if overrides == base_overrides:
            continue
        signature = case_request_signature(iface, overrides)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        seq += 1
        name = _compose_case_name(case_name_prefix, _case_name_suffix(d, seq))
        cases.append({
            "name": name,
            "description": _as_str(d.get("description"))[:1000],
            "priority": _normalize_priority(d.get("priority"), case_type, d.get("changes")),
            "case_type": case_type,
            "param_overrides": overrides,
            "assertions": assertion_for_case_type(case_type),
            "purpose": _as_str(d.get("purpose"))[:500],
            "warnings": (change_warnings + [_as_str(w) for w in _as_list(d.get("warnings"))])[:20],
            "todo": [_as_str(t) for t in _as_list(d.get("todo"))][:20],
        })
    return cases


def _normalize_priority(value: Any, case_type: str = "", changes: Any = None) -> str:
    p = _as_str(value).lower()
    if p not in ("low", "medium", "high"):
        p = "medium" if case_type in {"reverse", "abnormal"} else "high"
    if case_type == "reverse" and p == "high":
        items = [_as_dict(item) for item in _as_list(changes)]
        if items and all(_as_str(item.get("action")).lower() == "remove" or _missing_value(item.get("value")) for item in items):
            return "low"
        return "medium"
    return p


def _body_field_missing(iface: dict, field_path: str) -> bool:
    content = iface.get("body_content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            return True
    if not isinstance(content, dict):
        return True
    current: Any = content
    for segment in _as_str(field_path).split("."):
        if not isinstance(current, dict) or segment not in current:
            return True
        current = current[segment]
    return current is None or (isinstance(current, str) and not current.strip())


def build_system_generated_case(
    iface: dict,
    overrides: dict | None = None,
    change_warnings: list[str] | None = None,
) -> list[dict]:
    """根据已解析的接口数据生成一条基础请求用例，不调用 AI。"""
    request = build_param_overrides(iface, overrides)
    missing_required = []
    for field, label in (("query_params", "查询参数"), ("path_params", "路径参数"), ("headers", "请求头")):
        for item in _as_list(iface.get(field)):
            param = _as_dict(item)
            required = param.get("required") is True or str(param.get("required", "")).lower() == "true"
            key = _as_str(param.get("key") or param.get("name"))
            value = next((p.get("value") for p in _coerce_kv(request.get(field)) if _as_str(p.get("key")) == key), param.get("value"))
            if required and (value is None or (isinstance(value, str) and not value.strip())):
                missing_required.append(f"{label} {key or '未命名参数'}")
    body_iface = {**iface, "body_content": request.get("body_content")} if overrides is not None else iface
    for field_path in _as_list(iface.get("body_required_fields")):
        field_path = _as_str(field_path).strip()
        if field_path and _body_field_missing(body_iface, field_path):
            missing_required.append(f"请求体字段 {field_path}")

    todo = [f"请补充必填参数：{', '.join(missing_required)}"] if missing_required else []
    warnings = (list(change_warnings or []) + (["存在必填参数未提供示例值"] if missing_required else []))[:20]
    return [{
        "name": f"{iface.get('name') or iface.get('url') or '接口'}_基础用例",
        "description": "根据接口定义生成的基础请求用例，参数可能需要补充",
        "priority": "high",
        "case_type": "main",
        "param_overrides": request,
        "assertions": assertion_for_case_type("main"),
        "purpose": "提供接口请求模板，供用户检查、补充和执行",
        "warnings": warnings,
        "todo": todo,
    }]
