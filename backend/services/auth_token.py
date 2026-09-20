"""统一获取接口执行所需的鉴权令牌。"""
from __future__ import annotations

from collections.abc import Awaitable, Callable


class AuthTokenError(ValueError):
    """鉴权令牌获取失败，调用入口负责适配对外异常类型。"""


async def fetch_auth_token(
    auth: dict,
    auth_key: str | None = None,
    *,
    request_func: Callable[..., Awaitable[dict]] | None = None,
) -> str | None:
    """请求鉴权地址并按 JSONPath 提取令牌。"""
    url = auth.get("url")
    if not url:
        return None

    from services.execution_engine.variables import extract_jsonpath
    from services.proxy_config import select_proxy_for_url

    if request_func is None:
        from services.request_executor import execute_single_request
        request_func = execute_single_request
    request = request_func
    token_result = await request(
        method=auth.get("method", "GET"),
        url=url,
        headers=auth.get("headers", {}) or {},
        body=(
            auth.get("body")
            if isinstance(auth.get("body"), str)
            else str(auth.get("body")) if auth.get("body") else None
        ),
        timeout=30,
        proxy=select_proxy_for_url(url, auth.get("proxy_config")),
    )
    display_name = auth.get("name") or auth_key or "默认认证"
    if not token_result.get("success") or not token_result.get("response"):
        raise AuthTokenError(f"认证「{display_name}」获取令牌失败")

    response_body = token_result["response"].get("body")
    if not isinstance(response_body, dict):
        raise AuthTokenError(f"认证「{display_name}」响应不是 JSON，无法提取令牌")
    token_raw = extract_jsonpath(response_body, auth.get("jsonpath", "$.data.token"))
    if token_raw is None or token_raw == "":
        raise AuthTokenError(f"认证「{display_name}」未提取到令牌")
    return str(token_raw)
