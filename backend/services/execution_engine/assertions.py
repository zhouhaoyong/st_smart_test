"""Assertion evaluation against HTTP responses."""
import json
from typing import Any

from .variables import extract_jsonpath_result

# 历史写法与 AI 生成结果的操作符别名，统一收敛到一套口径
_OPERATOR_ALIASES = {"ne": "neq", "!=": "neq", "empty": "is_empty"}
# 只看实际值本身、不需要期望值的操作符
_OPERATORS_WITHOUT_EXPECTED = ("not_empty", "is_empty")


def normalize_assertion_operator(operator) -> str:
    """统一操作符写法，供断言执行与入库前的规范化共用。"""
    key = str(operator or "eq").strip()
    return _OPERATOR_ALIASES.get(key, key)


def default_business_code_assertion() -> dict:
    """返回新用例默认的业务码断言。"""
    return {
        "type": "jsonpath",
        "expression": "$.code",
        "operator": "eq",
        "expected": "200",
        "enabled": True,
    }


def normalize_assertions(assertions: list | None) -> list:
    """统一断言默认状态和操作符，保留用户明确关闭的断言。"""
    normalized = []
    for assertion in assertions or []:
        if not isinstance(assertion, dict):
            continue
        item = dict(assertion)
        item["enabled"] = item.get("enabled") is not False
        if item.get("operator"):
            item["operator"] = normalize_assertion_operator(item.get("operator"))
        normalized.append(item)
    return normalized


def ensure_business_code_assertion(assertions: list | None) -> list:
    """为新用例补充默认业务码断言；明确关闭的断言不会被重复添加。"""
    items = normalize_assertions(assertions)
    has_business_code = any(
        isinstance(item, dict)
        and item.get("type", "jsonpath") == "jsonpath"
        and str(item.get("expression", "")).strip() == "$.code"
        for item in items
    )
    return items if has_business_code else [default_business_code_assertion(), *items]


def _response_json(response_data: dict):
    if "json" in response_data:
        return response_data.get("json")
    body = response_data.get("body")
    return body if isinstance(body, (dict, list)) else None


def run_assertions(assertions: list, response_data: dict, duration_ms: int, logs: list) -> tuple[int, int, list]:
    """Run assertions against a response. Returns (passed, failed, diff_results)"""
    passed = 0
    failed = 0
    diffs = []

    for assertion in assertions:
        if not isinstance(assertion, dict) or assertion.get("enabled", True) is False:
            continue
        a_type = assertion.get("type", "jsonpath")
        expression = assertion.get("expression", "")
        operator = normalize_assertion_operator(assertion.get("operator", "eq"))
        expected = assertion.get("expected", "")

        actual = None
        # 除 JSONPath 之外的断言类型，实际值总是取得到
        actual_found = True
        if a_type == "jsonpath":
            json_body = _response_json(response_data) or {}
            actual, actual_found = extract_jsonpath_result(json_body, expression)
        elif a_type == "status_code":
            actual = response_data.get("status_code", 0)
        elif a_type == "response_time":
            actual = duration_ms
        elif a_type == "contains":
            json_body = _response_json(response_data)
            if json_body is not None:
                body_text = json.dumps(json_body, ensure_ascii=False)
            else:
                body_text = response_data.get("text", "") or response_data.get("body", "")
            actual = body_text
            # Default to contains operator for "contains" assertion type
            if operator == "eq":
                operator = "contains"

        # Compare
        result = _compare(actual, operator, expected, actual_found)

        diff_entry = {
            "type": a_type,
            "expression": expression,
            "operator": operator,
            "expected": expected,
            "actual": actual,
            "actual_found": actual_found,
            "result": "pass" if result else "fail",
        }
        diffs.append(diff_entry)

        if result:
            passed += 1
        else:
            failed += 1

    return passed, failed, diffs


def _normalize_val(v):
    """将值规范化为可比较的形式"""
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        # "true" / "false" → bool
        if s.lower() in ("true", "false"):
            return s.lower() == "true"
        # "null" / "none" → None
        if s.lower() in ("null", "none"):
            return None
        # 数字字符串
        if s.lstrip('-').replace('.', '').isdigit():
            return float(s) if '.' in s else int(s)
        return s
    return v


def _is_empty_value(actual: Any) -> bool:
    """空的判定口径：null、空字符串、空数组、空对象都算空；0 与 false 属于有值。"""
    if actual is None:
        return True
    if isinstance(actual, str):
        text = actual.strip()
        return text == "" or text.lower() in ("null", "none")
    if isinstance(actual, (list, dict)):
        return len(actual) == 0
    return False


def _compare(actual: Any, operator: str, expected: Any, actual_found: bool = True) -> bool:
    """Compare actual vs expected with the given operator"""
    try:
        if operator in _OPERATORS_WITHOUT_EXPECTED:
            # 字段取不到时「为空」「非空」一律判失败：路径写错不能被当成空而误判通过
            if not actual_found:
                return False
            is_empty = _is_empty_value(actual)
            return is_empty if operator == "is_empty" else not is_empty

        # 规范化为可比较形式
        a = _normalize_val(actual)
        e = _normalize_val(expected)

        if operator == "eq":
            # 类型相同直接比较
            if type(a) is type(e):
                return a == e
            # 数值比较
            if isinstance(a, (int, float, bool)) and isinstance(e, (int, float, bool)):
                return float(a) == float(e)
            # None 比较
            if a is None and e is None:
                return True
            # dict/list: JSON 序列化后比较
            if isinstance(a, (dict, list)) and isinstance(e, str):
                import json
                try:
                    return a == json.loads(e)
                except (json.JSONDecodeError, Exception):
                    pass
            if isinstance(actual, (dict, list)) and isinstance(expected, str):
                import json
                try:
                    return actual == json.loads(expected)
                except (json.JSONDecodeError, Exception):
                    pass
            # 兜底：字符串比较
            return str(actual) == str(expected)

        elif operator == "neq":
            # 复用 eq 逻辑取反
            return not _compare(actual, "eq", expected, actual_found)

        elif operator in ("gt", "lt", "gte", "lte"):
            try:
                fa = float(a) if a is not None else 0
                fe = float(e) if e is not None else 0
            except (ValueError, TypeError):
                fa = 0; fe = 0
            if operator == "gt":   return fa > fe
            if operator == "lt":   return fa < fe
            if operator == "gte":  return fa >= fe
            if operator == "lte":  return fa <= fe

        elif operator == "contains":
            return str(e) in str(actual) if actual is not None else False
    except (ValueError, TypeError):
        pass
    return False
