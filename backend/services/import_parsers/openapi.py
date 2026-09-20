"""
OpenAPI 3.0 / Swagger 2.0 解析。
从 import_api.py 原样搬运，行为保持一致。
"""
import json

from services.parameter_typing import infer_param_type, normalize_schema_type, schema_type_map


# ====== 解析 ======

def _resolve_ref(data: dict, ref: str) -> dict | None:
    """解析 $ref 引用，如 #/components/schemas/Pet"""
    if not ref or not ref.startswith("#/"):
        return None
    parts = ref[2:].split("/")
    current = data
    for p in parts:
        if isinstance(current, dict):
            current = current.get(p)
        else:
            return None
        if current is None:
            return None
    return current if isinstance(current, dict) else None


# 全局变量：暂存当前解析的原始数据，供 _schema_to_example 解析 $ref
_ref_data = None


def _resolved_schema(schema: dict) -> dict:
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema and _ref_data:
        return _resolve_ref(_ref_data, schema["$ref"]) or schema
    if "allOf" in schema and _ref_data:
        merged = {}
        for part in schema["allOf"]:
            p = _resolve_ref(_ref_data, part["$ref"]) if "$ref" in part else part
            if isinstance(p, dict):
                merged.update(p)
        return merged or schema
    return schema


def _resolved_schema_type_map(schema: dict) -> dict[str, str]:
    return {k: v for k, v in schema_type_map(_resolved_schema(schema)).items() if not k.endswith(".0")}


def _response_field_types(schema: dict, prefix: str = "", seen_refs: set[str] | None = None) -> dict[str, str]:
    """提取响应字段中明确声明的类型，未声明类型的不做猜测。"""
    resolved = _resolved_schema(schema)
    if not isinstance(resolved, dict):
        return {}
    properties = resolved.get("properties")
    if not isinstance(properties, dict):
        return {}
    seen_refs = set(seen_refs or ())
    result = {}
    for name, child in properties.items():
        field_path = f"{prefix}.{name}" if prefix else str(name)
        child_resolved = _resolved_schema(child)
        if isinstance(child_resolved, dict) and child_resolved.get("type") is not None:
            result[field_path] = normalize_schema_type(child_resolved)
        child_ref = child.get("$ref") if isinstance(child, dict) else None
        if child_ref and child_ref in seen_refs:
            continue
        next_seen_refs = seen_refs | {child_ref} if child_ref else seen_refs
        result.update(_response_field_types(child_resolved, field_path, next_seen_refs))
    return result


def _typed_param(param: dict, value: str = "") -> dict:
    if value in ("", None):
        value = _param_example_value(param)
    schema = param.get("schema") if isinstance(param, dict) else None
    has_schema = isinstance(schema, dict) or param.get("type")
    if isinstance(schema, dict):
        p_type = normalize_schema_type(_resolved_schema(schema))
    elif param.get("type"):
        p_type = normalize_schema_type({"type": param.get("type")})
    elif value not in ("", None):
        p_type = infer_param_type(value)
    else:
        p_type = "string"
    return {
        "key": param.get("name", ""),
        "value": value if value is not None else "",
        "description": param.get("description", ""),
        "required": bool(param.get("required")),
        "type": p_type,
        "type_source": "schema" if has_schema else "inferred" if value not in ("", None) else "default",
    }


def _param_example_value(param: dict):
    """提取 OpenAPI 参数示例值，优先级：example > schema.example > schema.default。"""
    if not isinstance(param, dict):
        return ""
    if "example" in param:
        return param.get("example")
    schema = param.get("schema")
    if isinstance(schema, dict):
        schema = _resolved_schema(schema)
        if "example" in schema:
            return schema.get("example")
        if "default" in schema:
            return schema.get("default")
    return ""

def _extract_body(iface: dict, content: dict):
    """从请求体 content 中提取 body_type 和 body_content"""
    if not content:
        return
    for ct in ["application/json", "text/json", "application/*+json"]:
        if ct in content:
            iface["body_type"] = "json"
            schema = content[ct].get("schema", {})
            iface["body_content"] = json.dumps(_schema_to_example(schema), ensure_ascii=False, indent=2)
            iface["body_schema_types"] = _resolved_schema_type_map(schema)
            iface["body_required_fields"] = _required_schema_fields(schema)
            return
    for ct in ["application/x-www-form-urlencoded", "multipart/form-data"]:
        if ct in content:
            cdata = content[ct]
            schema = cdata.get("schema", {})
            props = schema.get("properties", {})
            if props:
                iface["body_type"] = "form"
                iface["body_content"] = json.dumps({k: _schema_to_example(v, 0, k) for k, v in props.items()}, ensure_ascii=False, indent=2)
                iface["body_schema_types"] = {k: normalize_schema_type(_resolved_schema(v)) for k, v in props.items()}
                iface["body_required_fields"] = _required_schema_fields(schema)
            else:
                iface["body_type"] = "form"
            return
    for ct, cdata in content.items():
        if ct == "*/*": continue
        schema = cdata.get("schema", {})
        if schema:
            iface["body_type"] = "json"
            iface["body_content"] = json.dumps(_schema_to_example(schema), ensure_ascii=False, indent=2)
            iface["body_schema_types"] = _resolved_schema_type_map(schema)
            iface["body_required_fields"] = _required_schema_fields(schema)
            return


def _response_metadata(operation: dict) -> dict:
    """提取给推荐阶段使用的响应概况，不保存或发送完整响应内容。"""
    status_codes = []
    content_types = []
    top_level_fields = []
    field_types = {}
    field_type_conflicts = set()
    has_example = False
    responses = operation.get("responses", {}) if isinstance(operation, dict) else {}
    for status, response in responses.items():
        status_text = str(status)
        if status_text not in status_codes:
            status_codes.append(status_text)
        if not isinstance(response, dict):
            continue
        if "$ref" in response:
            response = _resolve_ref(_ref_data, response.get("$ref", "")) or response
        if response.get("examples"):
            has_example = True
        content = response.get("content", {})
        if isinstance(content, dict):
            for content_type, media in content.items():
                if content_type not in content_types:
                    content_types.append(content_type)
                if not isinstance(media, dict):
                    continue
                if "example" in media or media.get("examples"):
                    has_example = True
                schema = media.get("schema", {})
                resolved = _resolved_schema(schema)
                for name in (resolved.get("properties", {}) or {}):
                    if name not in top_level_fields:
                        top_level_fields.append(str(name))
                for field_name, field_type in _response_field_types(resolved).items():
                    if field_name not in field_types:
                        field_types[field_name] = field_type
                    elif field_types[field_name] != field_type:
                        field_types[field_name] = ""
                        field_type_conflicts.add(field_name)
        schema = response.get("schema", {})
        resolved = _resolved_schema(schema)
        for name in (resolved.get("properties", {}) or {}):
            if name not in top_level_fields:
                top_level_fields.append(str(name))
        for field_name, field_type in _response_field_types(resolved).items():
            if field_name not in field_types:
                field_types[field_name] = field_type
            elif field_types[field_name] != field_type:
                field_types[field_name] = ""
                field_type_conflicts.add(field_name)
    return {
        "status_codes": status_codes[:20],
        "content_types": content_types[:20],
        "has_example": has_example,
        "top_level_fields": top_level_fields[:20],
        "field_types": {
            name: value for name, value in list(field_types.items())[:50] if value
        },
        "field_type_conflicts": sorted(field_type_conflicts)[:50],
    }


def _json_text(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _response_example(operation: dict):
    """提取一个可供预览使用的响应示例，优先选择 2xx 响应。"""
    responses = operation.get("responses", {}) if isinstance(operation, dict) else {}
    if not isinstance(responses, dict):
        return None
    ordered = sorted(
        responses.items(),
        key=lambda item: (0 if str(item[0]).startswith("2") else 1, str(item[0])),
    )
    for _, response in ordered:
        if not isinstance(response, dict):
            continue
        if "$ref" in response:
            response = _resolve_ref(_ref_data, response.get("$ref", "")) or response
        examples = response.get("examples")
        if isinstance(examples, dict) and examples:
            first = next(iter(examples.values()))
            if isinstance(first, dict) and "value" in first:
                first = first.get("value")
            result = _json_text(first)
            if result is not None:
                return result
        content = response.get("content")
        if isinstance(content, dict):
            for media in content.values():
                if not isinstance(media, dict):
                    continue
                if "example" in media:
                    result = _json_text(media.get("example"))
                    if result is not None:
                        return result
                media_examples = media.get("examples")
                if isinstance(media_examples, dict) and media_examples:
                    first = next(iter(media_examples.values()))
                    if isinstance(first, dict) and "value" in first:
                        first = first.get("value")
                    result = _json_text(first)
                    if result is not None:
                        return result
    return None


def _required_schema_fields(schema: dict, prefix: str = "") -> list[str]:
    resolved = _resolved_schema(schema)
    if not isinstance(resolved, dict):
        return []
    result = []
    for name in resolved.get("required", []) or []:
        key = f"{prefix}.{name}" if prefix else str(name)
        result.append(key)
    properties = resolved.get("properties", {})
    if isinstance(properties, dict):
        for name, child in properties.items():
            child_prefix = f"{prefix}.{name}" if prefix else str(name)
            result.extend(_required_schema_fields(child, child_prefix))
    return result[:100]


def _document_info(data: dict) -> dict:
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    servers = []
    for server in data.get("servers", []) or []:
        if isinstance(server, dict) and server.get("url"):
            servers.append(str(server["url"]))
    if not servers and data.get("host"):
        schemes = data.get("schemes") or ["http"]
        base_path = str(data.get("basePath") or "").rstrip("/")
        servers = [f"{scheme}://{data['host']}{base_path}" for scheme in schemes]
    return {
        "title": str(info.get("title") or ""),
        "description": str(info.get("description") or ""),
        "version": str(info.get("version") or ""),
        "servers": servers[:20],
    }


def _auth_info(data: dict, operation: dict) -> dict:
    security = operation.get("security") if "security" in operation else data.get("security")
    schemes = []
    if isinstance(security, list):
        for requirement in security:
            if isinstance(requirement, dict):
                for name in requirement:
                    if str(name) not in schemes:
                        schemes.append(str(name))
    return {"required": bool(security), "schemes": schemes[:20]}


def _parse_openapi(data: dict, source: str) -> dict:
    """解析 OpenAPI 3.0 / Swagger 2.0，返回 {modules, interfaces}"""
    global _ref_data
    _ref_data = data
    modules = {}  # {"level1::level2": {level1_name, level2_name, interfaces: [...]}}
    interfaces = []

    # OpenAPI 3.0
    if data.get("openapi", "").startswith("3."):
        paths = data.get("paths", {})
        tags_map = {t["name"]: t for t in data.get("tags", [])}
        for path, methods in paths.items():
            for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                if method not in methods:
                    continue
                op = methods[method]
                # 提取一级和二级目录
                tags = op.get("tags", [])
                level1_name = tags[0] if len(tags) > 0 else ""
                # 只有一层目录时，二级目录留空，不要重复使用一级目录名
                level2_name = tags[1] if len(tags) > 1 else ""

                # 如果一级为空但二级有值，说明只解析出一层，将其作为一级
                if not level1_name and level2_name:
                    level1_name = level2_name
                    level2_name = ""

                # 构建模块key（用于去重）
                module_key = f"{level1_name}::{level2_name}"

                if module_key not in modules:
                    modules[module_key] = {
                        "level1_name": level1_name,
                        "level2_name": level2_name,
                        "interfaces": [],
                    }
                iface = {
                    "name": op.get("summary") or f"{method.upper()} {path}",
                    "method": method.upper(),
                    "url": path,
                    "description": op.get("description", ""),
                    "tags": op.get("tags", []),
                    "operation_id": op.get("operationId", ""),
                    "query_params": [],
                    "path_params": [],
                    "headers": [],
                    "body_type": None,
                    "body_content": None,
                    "body_schema_types": {},
                    "body_required_fields": [],
                    "needs_auth": _auth_info(data, op)["required"],
                    "auth_info": _auth_info(data, op),
                    "response_example": _response_example(op),
                    "response_meta": _response_metadata(op),
                    "pre_script": None,
                    "post_script": None,
                }
                # 提取参数（支持 $ref，含路径级参数 + 操作级参数，操作级覆盖路径级同名参数）
                seen_params = set()
                all_params = list(methods.get("parameters", [])) + list(op.get("parameters", []))
                for param in all_params:
                    pm = param
                    if "$ref" in pm:
                        pm = _resolve_ref(data, pm.get("$ref", "")) or pm
                    p_in = pm.get("in", "")
                    p_name = pm.get("name", "")
                    dedup_key = f"{p_in}:{p_name}"
                    if dedup_key in seen_params:
                        # 操作级覆盖路径级：移除旧条目再追加
                        if p_in == "query":
                            iface["query_params"] = [q for q in iface["query_params"] if q["key"] != p_name]
                        elif p_in == "path":
                            iface["path_params"] = [q for q in iface["path_params"] if q["key"] != p_name]
                        elif p_in == "header":
                            iface["headers"] = [h for h in iface["headers"] if h["key"] != p_name]
                    seen_params.add(dedup_key)
                    p = _typed_param(pm, _param_example_value(pm))
                    if p_in == "query":
                        iface["query_params"].append(p)
                    elif p_in == "path":
                        iface["path_params"].append(p)
                    elif p_in == "header":
                        iface["headers"].append(p)
                # 提取请求体（支持 $ref）
                if "requestBody" in op:
                    rb = op["requestBody"]
                    if "$ref" in rb:
                        rb = _resolve_ref(data, rb["$ref"]) or rb
                    content = rb.get("content", {}) if isinstance(rb, dict) else {}
                    _extract_body(iface, content)
                modules[module_key]["interfaces"].append(iface)
                interfaces.append(iface)

    # Swagger 2.0
    elif data.get("swagger", "").startswith("2."):
        paths = data.get("paths", {})
        tags_map = {t["name"]: t for t in data.get("tags", [])}
        for path, methods in paths.items():
            for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                if method not in methods:
                    continue
                op = methods[method]
                # 提取一级和二级目录
                tags = op.get("tags", [])
                level1_name = tags[0] if len(tags) > 0 else ""
                # 只有一层目录时，二级目录留空，不要重复使用一级目录名
                level2_name = tags[1] if len(tags) > 1 else ""

                # 如果一级为空但二级有值，说明只解析出一层，将其作为一级
                if not level1_name and level2_name:
                    level1_name = level2_name
                    level2_name = ""

                module_key = f"{level1_name}::{level2_name}"

                if module_key not in modules:
                    modules[module_key] = {
                        "level1_name": level1_name,
                        "level2_name": level2_name,
                        "interfaces": [],
                    }
                iface = {
                    "name": op.get("summary") or f"{method.upper()} {path}",
                    "method": method.upper(),
                    "url": path,
                    "description": op.get("description", ""),
                    "tags": op.get("tags", []),
                    "operation_id": op.get("operationId", ""),
                    "query_params": [],
                    "path_params": [],
                    "headers": [],
                    "body_type": None,
                    "body_content": None,
                    "body_schema_types": {},
                    "body_required_fields": [],
                    "needs_auth": _auth_info(data, op)["required"],
                    "auth_info": _auth_info(data, op),
                    "response_example": _response_example(op),
                    "response_meta": _response_metadata(op),
                    "pre_script": None,
                    "post_script": None,
                }
                # Swagger 2.0 参数 & Body（含路径级参数 + 操作级参数，操作级覆盖路径级同名参数）
                form_fields = {}
                form_required_fields = []
                seen_params = set()
                all_params = list(methods.get("parameters", [])) + list(op.get("parameters", []))
                for param in all_params:
                    # 解析 $ref
                    pm = param
                    if "$ref" in pm:
                        ref = pm.get("$ref", "")
                        pm = _resolve_ref(data, ref) or pm
                    p_in = pm.get("in", "")
                    p_name = pm.get("name", "")
                    dedup_key = f"{p_in}:{p_name}"
                    if dedup_key in seen_params:
                        if p_in == "query":
                            iface["query_params"] = [q for q in iface["query_params"] if q["key"] != p_name]
                        elif p_in == "path":
                            iface["path_params"] = [q for q in iface["path_params"] if q["key"] != p_name]
                        elif p_in == "header":
                            iface["headers"] = [h for h in iface["headers"] if h["key"] != p_name]
                        elif p_in == "formData":
                            form_fields.pop(p_name, None)
                    seen_params.add(dedup_key)
                    p_val = _typed_param(pm, pm.get("default", ""))
                    if p_in == "query":
                        iface["query_params"].append(p_val)
                    elif p_in == "path":
                        iface["path_params"].append(p_val)
                    elif p_in == "header":
                        iface["headers"].append(p_val)
                    elif p_in == "formData":
                        form_fields[p_name] = pm.get("default", "")
                        if pm.get("required") is True:
                            form_required_fields.append(p_name)
                    elif p_in == "body":
                        schema = pm.get("schema", {})
                        iface["body_type"] = "json"
                        iface["body_content"] = json.dumps(_schema_to_example(schema), ensure_ascii=False, indent=2)
                        iface["body_schema_types"] = _resolved_schema_type_map(schema)
                        iface["body_required_fields"] = _required_schema_fields(schema)
                # formData 转 JSON body
                if form_fields and not iface["body_type"]:
                    iface["body_type"] = "json"
                    iface["body_content"] = json.dumps(form_fields, ensure_ascii=False, indent=2)
                    iface["body_schema_types"] = {k: infer_param_type(v) for k, v in form_fields.items()}
                    iface["body_required_fields"] = form_required_fields
                modules[module_key]["interfaces"].append(iface)
                interfaces.append(iface)

    return {
        "modules": list(modules.values()),
        "total_interfaces": len(interfaces),
        "format": "openapi",
        "document_info": _document_info(data),
    }


def _schema_to_example(schema, depth=0, prop_name=""):
    """从 JSON Schema 生成示例 JSON（支持 $ref 和 allOf）"""
    if depth > 5:
        return {}
    if not isinstance(schema, dict):
        return schema
    # 解析 $ref
    if "$ref" in schema and _ref_data:
        resolved = _resolve_ref(_ref_data, schema["$ref"])
        if resolved:
            return _schema_to_example(resolved, depth + 1, prop_name)
        return {}
    if "example" in schema:
        return schema["example"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    # allOf 组合
    if "allOf" in schema:
        merged = {}
        for part in schema["allOf"]:
            p = _resolve_ref(_ref_data, part["$ref"]) if "$ref" in part else part
            if isinstance(p, dict):
                merged.update(p)
        if merged:
            return _schema_to_example(merged, depth + 1, prop_name)
    t = schema.get("type", "object")
    if t == "object":
        props = schema.get("properties", {})
        if not props:
            # 无 properties 但有 description，可能是空对象
            return {}
        return {k: _schema_to_example(v, depth + 1, k) for k, v in props.items()}
    elif t == "array":
        items = schema.get("items", {})
        return [_schema_to_example(items, depth + 1)] if items else []
    elif t == "string":
        if "default" in schema:
            return schema["default"]
        return ""
    elif t in ("integer", "number"):
        return schema.get("default")
    elif t == "boolean":
        return schema.get("default")
    if "properties" in schema:
        return {k: _schema_to_example(v, depth + 1, k) for k, v in schema["properties"].items()}
    return None
