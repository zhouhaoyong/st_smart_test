"""接口请求结构指纹。

文件导入与 cURL 导入用同一套口径判断
"这个接口结构有没有变化"，因此指纹计算集中在这里，
任何一处单独改口径都会让两条链路对同一份内容给出不同结论。

指纹**只取请求参数**：查询参数、路径参数、请求体结构。刻意不包含——

- 响应结构：文件导入不把响应落库，命令行导入根本没有响应，
  各来源覆盖度不一致，参与比对只会制造"结构有变化"的误判；
  响应变了也不会改接口和用例，交给断言在运行时暴露。
- 请求头：命令行导入带的是鉴权令牌、追踪标识这类运行时内容，
  与文档里声明式的请求头几乎不可能一致，是最大的噪声来源。
- 接口名称、描述、接口编号、示例取值：改个名字不该被判成结构变化。

同样重要的是：参与比对的字段必须都能在接口表里落库，
否则已落库的一侧永远算不出相同的指纹，会被永久判成"有变化"。
"""
from __future__ import annotations

import hashlib
import json


def normalized_type(value) -> str:
    """把解析器可能返回的类型名称归一成稳定文本。"""
    text = str(value or "").strip().lower()
    aliases = {
        "int": "integer",
        "long": "integer",
        "number": "float",
        "double": "float",
        "bool": "boolean",
    }
    return aliases.get(text, text)


def json_shape(value):
    """只提取 JSON 的形状，不把示例值写入接口结构指纹。"""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, dict):
        return {
            "object": {
                str(key): json_shape(child)
                for key, child in sorted(value.items(), key=lambda item: str(item[0]))
            },
        }
    if isinstance(value, list):
        shapes = {stable_json(json_shape(child)) for child in value}
        return {"array": [json.loads(shape) for shape in sorted(shapes)]}
    return str(type(value).__name__)


def stable_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parameter_structure(items) -> list[dict]:
    result = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        result.append({
            "key": str(item.get("key") or item.get("name") or ""),
            "type": normalized_type(item.get("type") or item.get("schema_type") or "string"),
            "required": bool(item.get("required")),
        })
    return sorted(result, key=stable_json)


def type_map(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): normalized_type(item)
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
    }


def interface_structure_data(iface: dict) -> dict:
    return {
        "query_params": parameter_structure(iface.get("query_params")),
        "path_params": parameter_structure(iface.get("path_params")),
        "body": {
            "type": str(iface.get("body_type") or ""),
            "schema_types": type_map(iface.get("body_schema_types")),
            "example_shape": json_shape(iface.get("body_content")),
        },
    }


def interface_structure_fingerprint(iface: dict) -> str:
    """生成只与请求参数结构有关的摘要。"""
    payload = stable_json(interface_structure_data(iface))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def existing_interface_structure_fingerprint(existing) -> str:
    """按已落库字段实时重算指纹，不读历史存下来的那一列。

    口径调整过之后，历史指纹与当前算法不再对应；而参与比对的字段现在
    全部都能从接口表里取到，实时重算永远自洽，也就不需要数据迁移。
    """
    return interface_structure_fingerprint({
        "query_params": getattr(existing, "query_params", None),
        "path_params": getattr(existing, "path_params", None),
        "body_type": getattr(existing, "body_type", None),
        "body_content": getattr(existing, "body_content", None),
        "body_schema_types": getattr(existing, "body_schema_types", None),
    })
