"""
导入解析公共工具：格式识别。
"""


def _detect_format(data: dict) -> str:
    if "openapi" in data:
        return "openapi"
    if "swagger" in data:
        return "openapi"
    if "info" in data and "item" in data and isinstance(data.get("item"), list):
        # Check if it's Postman (has request/url structure)
        def _has_request(items):
            for it in items:
                if "request" in it:
                    return True
                if "item" in it and _has_request(it["item"]):
                    return True
            return False
        if _has_request(data.get("item", [])):
            return "postman"
    return "unknown"
