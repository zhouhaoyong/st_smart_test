"""JSONPath 提取工具接口。"""
from __future__ import annotations

import json

from ._shared import (
    APIRouter,
    BaseModel,
    Depends,
    UnifiedException,
    get_current_active_user,
    get_db,
    AsyncSession,
    log_user_operation,
    success_response,
)

router = APIRouter()


# ====== JSONPath 提取工具 ======


class JsonExtractRequest(BaseModel):
    response: str


class JsonInspectRequest(BaseModel):
    """断言编辑器里的字段选取：解析响应并按路径试取值。"""

    response: str
    expression: str = ""
    include_tree: bool = True


def _escape_json_path_key(key):
    """将 key 转为 JSONPath 片段"""
    if isinstance(key, int):
        return f'[{key}]'
    if isinstance(key, str) and key.isidentifier():
        return f'.{key}'
    escaped = str(key).replace('\\', '\\\\').replace("'", "\\'")
    return f"['{escaped}']"


def _build_json_tree(value, path='$', label='root'):
    """递归构建 JSON 字段树"""
    node_type = type(value).__name__
    if isinstance(value, dict):
        children = [
            _build_json_tree(v, f"{path}{_escape_json_path_key(k)}", str(k))
            for k, v in value.items()
        ]
        return {
            'label': label,
            'path': path,
            'type': 'object',
            'value': value,
            'children': children,
            'preview': f'Object({len(value)})'
        }
    if isinstance(value, list):
        children = [
            _build_json_tree(v, f'{path}[{idx}]', f'[{idx}]')
            for idx, v in enumerate(value)
        ]
        return {
            'label': label,
            'path': path,
            'type': 'array',
            'value': value,
            'children': children,
            'preview': f'Array({len(value)})'
        }
    return {
        'label': label,
        'path': path,
        'type': node_type,
        'value': value,
        'children': [],
        'preview': repr(value)
    }


@router.post("/extract")
async def json_path_extract(
    data: JsonExtractRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """解析接口响应 JSON，生成 JSONPath 字段树"""
    response_text = (data.response or '').strip()
    if not response_text:
        raise UnifiedException(code=400, message="response 字段不能为空")

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise UnifiedException(code=400, message=f"接口响应不是合法 JSON: {exc}")

    tree = _build_json_tree(parsed)
    await log_user_operation(
        db=db,
        user=current_user,
        module="json_tool",
        operation="解析",
        target_name="JSONPath 提取",
        description="解析 JSON 并提取 JSONPath",
        details={"root_type": type(parsed).__name__},
    )
    return success_response(data={"tree": tree})


@router.post("/inspect")
async def json_path_inspect(
    data: JsonInspectRequest,
    current_user=Depends(get_current_active_user),
):
    """断言编辑器专用：解析响应生成字段树，并按表达式试取值。

    与提取工具的差别是：取值口径直接复用执行引擎，保证「选取时看到的值」和
    「运行时断言拿到的值」完全一致；同时这是编辑器辅助操作而非工具使用，
    不写操作审计，避免刷满审计记录。
    """
    response_text = (data.response or '').strip()
    if not response_text:
        raise UnifiedException(code=400, message="响应内容不能为空")

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise UnifiedException(code=400, message=f"响应内容不是合法 JSON：{exc}")

    result = {
        "tree": _build_json_tree(parsed) if data.include_tree else None,
        "expression": data.expression or "",
        "value": None,
        "found": False,
    }
    expression = (data.expression or '').strip()
    if expression:
        from services.execution_engine import extract_jsonpath_result

        value, found = extract_jsonpath_result(parsed, expression)
        result["value"] = value
        result["found"] = found
    return success_response(data=result)
