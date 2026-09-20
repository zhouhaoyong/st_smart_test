"""
Postman Collection v2.1 解析。
从 import_api.py 原样搬运，行为保持一致。
"""
import json
import re

from services.parameter_typing import infer_param_type


# 全局变量：与 import_api 原实现保持一致（Postman 解析不依赖 $ref，但保留赋值以维持行为）
_ref_data = None


def _response_value_type(value):
    """按 JSON 解析后的真实值判断类型，不把数字字符串误判为整型。"""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, str):
        return "string"
    return ""


def _response_metadata(item: dict) -> dict:
    """从 Postman 保存的响应样例提取概况，不发送响应正文。"""
    status_codes = []
    content_types = []
    top_level_fields = []
    field_types = {}
    field_type_conflicts = set()
    has_example = False
    for response in item.get("response", []) or []:
        if not isinstance(response, dict):
            continue
        if response.get("code") is not None:
            status = str(response["code"])
            if status not in status_codes:
                status_codes.append(status)
        for header in response.get("header", []) or []:
            if not isinstance(header, dict) or str(header.get("key", "")).lower() != "content-type":
                continue
            content_type = str(header.get("value", ""))
            if content_type and content_type not in content_types:
                content_types.append(content_type)
        body = response.get("body")
        if body not in (None, ""):
            has_example = True
            if isinstance(body, str):
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        for name, value in parsed.items():
                            if str(name) not in top_level_fields:
                                top_level_fields.append(str(name))
                            if value is not None:
                                inferred_type = _response_value_type(value)
                                field_name = str(name)
                                previous_type = field_types.get(field_name)
                                if previous_type is None:
                                    field_types[field_name] = inferred_type
                                elif previous_type != inferred_type:
                                    field_types[field_name] = ""
                                    field_type_conflicts.add(field_name)
                except (TypeError, ValueError):
                    pass
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


def _response_example(item: dict):
    for response in item.get("response", []) or []:
        if not isinstance(response, dict):
            continue
        body = response.get("body")
        if body in (None, ""):
            continue
        if isinstance(body, str):
            try:
                return json.dumps(json.loads(body), ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                return body
        return json.dumps(body, ensure_ascii=False, indent=2)
    return None


def _path_params(url_info: dict, path: str) -> list[dict]:
    variables = url_info.get("variable") if isinstance(url_info, dict) else None
    variable_map = {
        str(item.get("key")): item
        for item in (variables or [])
        if isinstance(item, dict) and item.get("key")
    }
    names = []
    for match in re.finditer(r":([A-Za-z0-9_.-]+)|\{([^{}]+)\}|\{\{([^{}]+)\}\}", path or ""):
        name = next(group for group in match.groups() if group)
        if name not in names:
            names.append(name)
    for name in variable_map:
        if name not in names:
            names.append(name)
    result = []
    for name in names:
        item = variable_map.get(name, {})
        value = item.get("value", "")
        result.append({
            "key": name,
            "value": value,
            "description": item.get("description", ""),
            "type": infer_param_type(value),
            "type_source": "inferred",
            "required": True,
        })
    return result


def _parse_postman(data: dict, source: str) -> dict:
    """解析 Postman Collection v2.1，支持两层嵌套"""
    global _ref_data
    _ref_data = data
    modules = {}  # {"level1::level2": {level1_name, level2_name, interfaces: [...]}}
    info = data.get("info", {})
    default_module = info.get("name", "Postman导入")

    def process_items(items, level1_name=None, level2_name=None, depth=0):
        for item in items:
            if "item" in item:  # 文件夹
                folder_name = item.get("name", "未命名")
                if depth == 0:
                    # 第一层文件夹 -> 一级目录
                    process_items(item["item"], level1_name=folder_name, level2_name=None, depth=1)
                elif depth == 1:
                    # 第二层文件夹 -> 二级目录
                    process_items(item["item"], level1_name=level1_name, level2_name=folder_name, depth=2)
                else:
                    # 第三层及以后，合并到第二层
                    process_items(item["item"], level1_name=level1_name, level2_name=level2_name, depth=depth+1)
            elif "request" in item:  # 请求
                # 确定最终的一级和二级目录名
                # 如果只有一级目录，保留一级，二级留空
                # 如果两级都有，都保留
                # 如果都没有，使用默认模块作为一级
                if level1_name and not level2_name:
                    # 只有一级目录的情况
                    final_level1 = level1_name
                    final_level2 = ""
                elif level2_name:
                    # 两级都有的情况
                    final_level1 = level1_name or ""
                    final_level2 = level2_name
                else:
                    # 都没有的情况
                    final_level1 = default_module
                    final_level2 = ""

                module_key = f"{final_level1}::{final_level2}"
                if module_key not in modules:
                    modules[module_key] = {
                        "level1_name": final_level1,
                        "level2_name": final_level2,
                        "interfaces": []
                    }
                req = item["request"]
                url_info = req.get("url", {})
                if isinstance(url_info, dict):
                    path = "/" + "/".join(url_info.get("path", []))
                    if not path.startswith("/"):
                        path = "/" + path
                    # 提取 query 参数
                    query_params = [{"key": q.get("key", ""), "value": q.get("value", ""), "description": q.get("description", ""),
                                     "type": infer_param_type(q.get("value", "")), "type_source": "inferred"}
                                    for q in (url_info.get("query") or []) if q.get("key")]
                else:
                    path = url_info if isinstance(url_info, str) else "/"
                    query_params = []
                method = req.get("method", "GET").upper()
                auth = req.get("auth") if isinstance(req.get("auth"), dict) else {}
                auth_type = str(auth.get("type") or "").strip()
                auth_info = {"required": bool(auth_type and auth_type.lower() != "noauth"), "schemes": [auth_type] if auth_type else []}
                body = req.get("body", {})
                body_type = None
                body_content = None
                if body:
                    mode = body.get("mode", "")
                    if mode == "raw":
                        body_type = "json"
                        body_content = body.get("raw", "")
                    elif mode == "urlencoded":
                        params = body.get("urlencoded", [])
                        if params:
                            body_type = "form"
                            body_content = json.dumps({p.get("key", ""): p.get("value", "") for p in params if p.get("key")}, ensure_ascii=False, indent=2)
                    elif mode == "formdata":
                        body_type = "form"
                iface = {
                    "name": item.get("name", f"{method} {path}"),
                    "method": method,
                    "url": path,
                    "description": item.get("name", ""),
                    "tags": [final_level2],
                    "operation_id": "",
                    "query_params": query_params,
                    "path_params": _path_params(url_info if isinstance(url_info, dict) else {}, path),
                    "headers": [{"key": h["key"], "value": h.get("value", ""), "description": ""}
                                | {"type": infer_param_type(h.get("value", "")), "type_source": "inferred"}
                                for h in req.get("header", []) if h.get("key")],
                    "body_type": body_type,
                    "body_content": body_content,
                    "body_schema_types": {},
                    "body_required_fields": [],
                    "needs_auth": auth_info["required"],
                    "auth_info": auth_info,
                    "response_example": _response_example(item),
                    "response_meta": _response_metadata(item),
                    "pre_script": None,
                    "post_script": None,
                }
                modules[module_key]["interfaces"].append(iface)

    items = data.get("item", [])
    process_items(items)
    total = sum(len(m["interfaces"]) for m in modules.values())
    return {"modules": list(modules.values()), "total_interfaces": total, "format": "postman"}
