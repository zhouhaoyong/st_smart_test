"""Variable handling, placeholder resolution, and the script execution context."""
import re
import json
from typing import Any
from urllib.parse import quote


class DotDict(dict):
    """A dict subclass that supports attribute-style access (request.body.task_name).

    Enables Postman-compatible scripts: pm.request.body, pm.response.headers, etc.
    Setting an attribute on a non-existent key auto-creates a nested DotDict.
    """
    def __getattr__(self, key):
        try:
            val = self[key]
        except KeyError:
            # Auto-create nested dict for attribute-style assignment
            val = DotDict()
            self[key] = val
        if isinstance(val, dict) and not isinstance(val, DotDict):
            val = DotDict(val)
            self[key] = val
        return val

    def __setattr__(self, key, value):
        if key.startswith("_"):
            super().__setattr__(key, value)
        else:
            self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)


class ScriptContext:
    """Script execution context providing a Postman-like API (pm.*)"""

    def __init__(self):
        self._variables = {}
        self.request = DotDict()
        self.response = None

    class Variables:
        def __init__(self, store):
            self._store = store

        def get(self, key):
            return self._store.get(key)

        def set(self, key, value):
            self._store[key] = value

    class ResponseWrapper:
        def __init__(self, response_obj):
            self.status = response_obj.get("status_code", 0)
            self.headers = response_obj.get("headers", {})
            self._text = response_obj.get("text", "")
            self._json_data = response_obj.get("json")

        @property
        def text(self):
            return self._text

        def json(self):
            return self._json_data if self._json_data is not None else {}

    def build_api(self):
        self._api = DotDict({
            "pm": DotDict({
                "variables": self.Variables(self._variables),
                "request": self.request,
                "response": self.ResponseWrapper(self.response) if self.response else None,
                "environment": self._variables,
            }),
        })
        return self._api

    def execute(self, script: str) -> str:
        """Execute a script and return log output"""
        logs = []
        api = self.build_api()

        def log_print(*args):
            logs.append(" ".join(str(a) for a in args))

        api["console"] = {"log": log_print}
        api["print"] = log_print
        # Expose request/response as bare variables for Postman-compatible scripts
        api["request"] = self.request
        api["response"] = self.ResponseWrapper(self.response) if self.response else None

        # Allow-list of builtins and platform modules that scripts can safely use
        import builtins as _builtins
        safe_globals = {
            "__builtins__": {
                "True": True, "False": False, "None": None,
                "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "tuple": tuple, "set": set,
                "len": len, "range": range, "enumerate": enumerate, "zip": zip,
                "abs": abs, "min": min, "max": max, "sum": sum, "round": round,
                "isinstance": isinstance, "type": type,
                "print": log_print,
                "__import__": _builtins.__import__,
            },
        }
        # Inject platform stdlib modules that scripts frequently use
        for mod_name in ("json", "time", "datetime", "random", "re", "math", "hashlib", "base64"):
            try:
                safe_globals[mod_name] = __import__(mod_name)
            except ImportError:
                pass

        try:
            exec(script, safe_globals, api)
        except Exception as e:
            logs.append(f"[Script Error] {e}")

        return "\n".join(logs)


def resolve_variables(text: str, variables: dict) -> str:
    """Resolve {{variable}} and $.variable placeholders in text.

    Priority: {{variable}} first, then $.variable from globals.
    $.variable syntax resolves against the top-level keys of the variables dict.
    $scenario.variable resolves against variables["scenario"] and stays isolated
    from normal $.variable parameter-set/environment values.
    """
    if not text or not isinstance(text, str):
        return text

    def replace_match(m):
        brace_content = m.group(1).strip()
        brace_key = brace_content.split('.', 1)[0] if '.' in brace_content else brace_content
        return str(variables.get(brace_key, m.group(0)))

    # 1. Resolve {{variable}} syntax
    text = re.sub(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}", replace_match, text)

    def resolve_path(path: str, root: Any) -> Any:
        parts = path.split(".")
        val = root
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return None
        return val

    # 2. Resolve $scenario.variable syntax in its own namespace
    def resolve_scenario_match(m):
        val = resolve_path(m.group(1), variables.get("scenario", {}) if isinstance(variables, dict) else {})
        return m.group(0) if val is None else str(val)

    text = re.sub(r"\$scenario\.([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)", resolve_scenario_match, text)

    # 3. Resolve $.variable syntax (JSONPath-style references to global variables)
    def resolve_jsonpath_match(m):
        val = resolve_path(m.group(1), variables)
        return m.group(0) if val is None else str(val)

    text = re.sub(r"\$\.([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)", resolve_jsonpath_match, text)

    return text


def resolve_dict(obj: Any, variables: dict) -> Any:
    """Recursively resolve variables in a dict/list/string"""
    if isinstance(obj, str):
        return resolve_variables(obj, variables)
    elif isinstance(obj, dict):
        return {k: resolve_dict(v, variables) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_dict(item, variables) for item in obj]
    return obj


def cast_parameter_value(value: Any, param_type: str | None) -> Any:
    if param_type == "int":
        return int(str(value).strip())
    if param_type == "float":
        return float(str(value).strip())
    if param_type == "bool":
        text = str(value).strip().lower()
        if text == "true":
            return True
        if text == "false":
            return False
        return value
    if param_type in ("list", "object"):
        return json.loads(value) if isinstance(value, str) else value
    return value


def resolve_typed_value(value: Any, variables: dict) -> Any:
    """Resolve variables, preserving configured parameter types for full-value refs."""
    if not isinstance(value, str):
        return value

    parameter_types = variables.get("__parameter_types", {}) if isinstance(variables, dict) else {}

    brace_match = re.fullmatch(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}", value)
    jsonpath_match = re.fullmatch(r"\$\.([A-Za-z0-9_-]+)", value)
    scenario_match = re.fullmatch(r"\$scenario\.([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)", value)
    key = None
    if scenario_match:
        val = variables.get("scenario", {}) if isinstance(variables, dict) else {}
        for part in scenario_match.group(1).split("."):
            if isinstance(val, dict) and part in val:
                val = val[part]
            else:
                val = None
                break
        if val is not None:
            return val
    if brace_match:
        key = brace_match.group(1).split(".", 1)[0]
    elif jsonpath_match:
        key = jsonpath_match.group(1)

    if key and key in variables:
        return cast_parameter_value(variables[key], parameter_types.get(key))

    return resolve_variables(value, variables)


def resolve_typed_dict(obj: Any, variables: dict) -> Any:
    if isinstance(obj, str):
        return resolve_typed_value(obj, variables)
    if isinstance(obj, dict):
        return {k: resolve_typed_dict(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_typed_dict(item, variables) for item in obj]
    return obj


def resolve_json_with_typed_variables(raw: str | dict | list, variables: dict) -> Any:
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    return resolve_typed_dict(parsed, variables)


def substitute_path_params(url: str, path_params: list | None, variables: dict) -> str:
    """Replace OpenAPI-style path placeholders with configured path parameter values."""
    if not url or not isinstance(url, str) or not path_params:
        return url

    resolved_url = url
    for item in path_params:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        raw_value = item.get("value", "")
        raw_text = str(raw_value)
        value = resolve_variables(raw_text, variables)
        unresolved_pattern = r"\$\.([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)|\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}"
        encoded_value = value if value == raw_text and re.search(unresolved_pattern, value) else quote(value, safe="")
        resolved_url = resolved_url.replace(f"{{{key}}}", encoded_value)
        resolved_url = re.sub(rf":{re.escape(key)}(?=/|$)", encoded_value, resolved_url)
    return resolved_url


# 取值失败的哨兵：用于区分「字段不存在」和「字段存在但值为 null」
_JSONPATH_MISSING = object()


def _unescape_jsonpath_key(text: str, quote_char: str) -> str:
    """还原方括号写法里被转义的字段名，与字段树生成路径时的转义规则对应。"""
    return text.replace(f"\\{quote_char}", quote_char).replace("\\\\", "\\")


def _tokenize_jsonpath(path: str) -> list | None:
    """把路径拆成取值步骤：字符串表示对象字段，整数表示数组下标；无法解析时返回 None。

    支持 $.key.subkey、$.array[0].key、$[0].key，以及字段名无法直接用点号连接时的
    $['field-name'] / $["field name"] 写法，与 JSONPath 提取工具生成的路径保持一致。
    """
    if not path:
        return None
    text = str(path).strip()
    if not text.startswith("$"):
        return None

    rest = text[1:]
    # 容忍 $key 这类省略首个点号的历史写法
    if rest and rest[0] not in ".[":
        rest = f".{rest}"

    tokens: list = []
    index = 0
    length = len(rest)
    while index < length:
        char = rest[index]
        if char == ".":
            index += 1
            start = index
            while index < length and rest[index] not in ".[":
                index += 1
            field = rest[start:index]
            # 容忍 $.data. 这类多余的点号，保持与历史写法的兼容
            if field:
                tokens.append(field)
            continue
        if char == "[":
            end = rest.find("]", index + 1)
            if end == -1:
                return None
            inner = rest[index + 1:end].strip()
            index = end + 1
            if len(inner) >= 2 and inner[0] == inner[-1] and inner[0] in ("'", '"'):
                tokens.append(_unescape_jsonpath_key(inner[1:-1], inner[0]))
                continue
            if inner.isdigit():
                tokens.append(int(inner))
                continue
            return None
        return None
    return tokens


def _walk_jsonpath(data: Any, tokens: list) -> Any:
    """按取值步骤逐层下钻，任意一层取不到就返回哨兵。"""
    current = data
    for token in tokens:
        if isinstance(token, int):
            if isinstance(current, list) and 0 <= token < len(current):
                current = current[token]
            else:
                return _JSONPATH_MISSING
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            return _JSONPATH_MISSING
    return current


def extract_jsonpath_result(data: Any, path: str) -> tuple[Any, bool]:
    """按简易 JSONPath 取值，返回 (值, 是否取到)。

    取不到时值为 None；配合布尔位可以区分「字段不存在」和「字段存在但值为 null」，
    断言的空值判定依赖这个区分，避免路径写错时被当成「空」而误判通过。
    """
    tokens = _tokenize_jsonpath(path)
    if tokens is None:
        return None, False
    # 只写 $ 表示整个响应体（断言表达式可自由输入，这里避免越界）
    value = _walk_jsonpath(data, tokens)
    if value is _JSONPATH_MISSING:
        return None, False
    return value, True


def extract_jsonpath(data: dict, path: str) -> Any:
    """按简易 JSONPath 取值，取不到返回 None（变量提取等既有调用方依赖该行为）。"""
    value, _ = extract_jsonpath_result(data, path)
    return value
