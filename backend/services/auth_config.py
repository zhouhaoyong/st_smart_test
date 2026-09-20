import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Awaitable, Callable


AUTH_HEADER_PRESETS = {
    "authorization",
    "x-auth-token",
    "x-api-key",
    "x-access-token",
    "cookie",
    "token",
    "access_token",
    "jwt",
}


# 仅在当前后端进程内缓存动态认证 Token，不保存到接口、用例或数据库。
_AUTH_TOKEN_CACHE: dict[tuple[str, str, str], str] = {}
_AUTH_TOKEN_LOCKS: dict[tuple[str, str, str], asyncio.Lock] = {}


@dataclass
class AuthResolution:
    headers: dict
    auth: dict | None = None
    source: str = "none"
    token: str | None = None


def _clean_key(value, fallback: str = "") -> str:
    return str(value or fallback).strip()


def _is_new_auth_config(config: dict | None) -> bool:
    return isinstance(config, dict) and ("items" in config or "default_auth_key" in config)


def normalize_auth_item(raw: dict | None, fallback_key: str = "default", fallback_name: str = "默认认证") -> dict:
    raw = raw if isinstance(raw, dict) else {}
    key = _clean_key(raw.get("key"), fallback_key)
    return {
        "key": key,
        "name": _clean_key(raw.get("name"), fallback_name),
        "enabled": raw.get("enabled", True) is True,
        "method": _clean_key(raw.get("method"), "POST").upper(),
        "url": _clean_key(raw.get("url")),
        "jsonpath": _clean_key(raw.get("jsonpath"), "$.data.token"),
        "body": raw.get("body", "{}"),
        "headers": raw.get("headers") if isinstance(raw.get("headers"), dict) else {},
        "token_prefix": str(raw.get("token_prefix", "Bearer ")),
        "header_key": _clean_key(raw.get("header_key"), "Authorization"),
        "manual_token": str(raw.get("manual_token") or ""),
        "proxy_config": raw.get("proxy_config") if isinstance(raw.get("proxy_config"), dict) else {},
    }


def normalize_auth_config(config: dict | None) -> dict:
    if not isinstance(config, dict) or not config:
        return {"default_auth_key": "", "items": []}

    if not _is_new_auth_config(config):
        item = normalize_auth_item(config, "default", "默认认证")
        return {"default_auth_key": item["key"], "items": [item]}

    items = []
    seen = set()
    for index, raw in enumerate(config.get("items") or []):
        if not isinstance(raw, dict):
            continue
        item = normalize_auth_item(raw, f"auth_{index + 1}", raw.get("name") or f"认证 {index + 1}")
        if not item["key"] or item["key"] in seen:
            continue
        seen.add(item["key"])
        items.append(item)

    default_auth_key = _clean_key(config.get("default_auth_key"))
    if default_auth_key and not any(item["key"] == default_auth_key for item in items):
        default_auth_key = ""
    return {"default_auth_key": default_auth_key, "items": items}


def get_auth_config(auth_config: dict | None, service: dict | None = None) -> tuple[dict | None, str]:
    normalized = normalize_auth_config(auth_config)
    items = {item["key"]: item for item in normalized["items"]}

    def is_usable(auth: dict | None) -> bool:
        return bool(auth and (auth.get("enabled") is True or str(auth.get("manual_token") or "").strip()))

    service_auth_key = _clean_key((service or {}).get("auth_key"))
    if service_auth_key:
        auth = items.get(service_auth_key)
        if is_usable(auth):
            return auth, "service"
        return None, "service_invalid"

    default_key = normalized.get("default_auth_key")
    if default_key:
        auth = items.get(default_key)
        if is_usable(auth):
            return auth, "default"
        return None, "default_invalid"

    return None, "none"


def has_auth_header(headers: dict | None, header_key: str = "Authorization") -> bool:
    if not isinstance(headers, dict):
        return False
    target = _clean_key(header_key, "Authorization").lower()
    return any(str(key or "").strip().lower() == target for key in headers)


def has_any_auth_header(headers: dict | None) -> bool:
    if not isinstance(headers, dict):
        return False
    return any(str(key or "").strip().lower() in AUTH_HEADER_PRESETS for key in headers)


def apply_auth_to_headers(headers: dict | None, token: str, auth: dict, preserve_existing: bool = True) -> dict:
    result = dict(headers or {})
    header_key = _clean_key(auth.get("header_key"), "Authorization")
    if preserve_existing and has_auth_header(result, header_key):
        return result
    prefix = str(auth.get("token_prefix", "Bearer "))
    existing_key = next((key for key in result if str(key).lower() == header_key.lower()), None)
    result[existing_key or header_key] = f"{prefix}{token}"
    return result


def manual_token_from_auth(auth: dict | None) -> str | None:
    if not auth:
        return None
    enabled = auth.get("enabled", True) is True
    manual_token = str(auth.get("manual_token") or "").strip()
    if enabled or not manual_token:
        return None
    prefix = str(auth.get("token_prefix", "Bearer ")).strip()
    if prefix and manual_token.lower().startswith(prefix.lower()):
        return manual_token[len(prefix):].strip()
    return manual_token


async def resolve_auth_headers(
    *,
    headers: dict | None,
    auth_config: dict | None,
    service: dict | None,
    token_fetcher: Callable[[dict, str], Awaitable[str | None]],
    execution_context: dict | None = None,
    explicit_auth_header: bool | None = None,
    auth_cache_scope: str | int | None = None,
    force_refresh: bool = False,
    stale_token: str | None = None,
) -> AuthResolution:
    headers = dict(headers or {})
    if explicit_auth_header is True or (explicit_auth_header is None and has_any_auth_header(headers)):
        return AuthResolution(headers=headers, source="manual_header")

    auth, source = get_auth_config(auth_config, service)
    if not auth:
        return AuthResolution(headers=headers, source=source)

    auth_key = auth["key"]
    token = manual_token_from_auth(auth)
    if not token:
        if execution_context is not None:
            tokens = execution_context.setdefault("tokens", {})
            if not force_refresh and auth_key in tokens:
                token = tokens[auth_key]
            elif force_refresh and stale_token:
                current_token = tokens.get(auth_key)
                if current_token and current_token != stale_token:
                    token = current_token
                else:
                    tokens.pop(auth_key, None)
        if not token:
            token = await _get_cached_auth_token(
                auth=auth,
                auth_key=auth_key,
                token_fetcher=token_fetcher,
                cache_scope=auth_cache_scope,
                force_refresh=force_refresh,
                stale_token=stale_token,
            )
        if token and execution_context is not None:
            execution_context.setdefault("tokens", {})[auth_key] = token

    if not token:
        raise ValueError(f"认证「{auth.get('name') or auth_key}」未获取到令牌")

    return AuthResolution(
        headers=apply_auth_to_headers(headers, token, auth, preserve_existing=False),
        auth=auth,
        source=source,
        token=token,
    )


def _auth_cache_key(auth: dict, auth_key: str, cache_scope: str | int) -> tuple[str, str, str]:
    """按环境和认证配置隔离缓存，避免不同环境共用 Token。"""
    fingerprint_source = json.dumps(auth, ensure_ascii=False, sort_keys=True, default=str)
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    return str(cache_scope), auth_key, fingerprint


async def _get_cached_auth_token(
    *,
    auth: dict,
    auth_key: str,
    token_fetcher: Callable[[dict, str], Awaitable[str | None]],
    cache_scope: str | int | None,
    force_refresh: bool = False,
    stale_token: str | None = None,
) -> str | None:
    """读取或获取 Token；刷新时只替换已经确认失效的旧 Token。"""
    if cache_scope is None:
        return await token_fetcher(auth, auth_key)

    cache_key = _auth_cache_key(auth, auth_key, cache_scope)
    cached = _AUTH_TOKEN_CACHE.get(cache_key)
    if cached and not force_refresh:
        return cached

    lock = _AUTH_TOKEN_LOCKS.setdefault(cache_key, asyncio.Lock())
    async with lock:
        cached = _AUTH_TOKEN_CACHE.get(cache_key)
        if force_refresh:
            # 并发请求中已有请求完成刷新时，直接复用新 Token，避免重复登录。
            if stale_token and cached and cached != stale_token:
                return cached
            if stale_token and cached == stale_token:
                _AUTH_TOKEN_CACHE.pop(cache_key, None)
        elif cached:
            return cached

        token = await token_fetcher(auth, auth_key)
        if token:
            _AUTH_TOKEN_CACHE[cache_key] = str(token)
        return token


def is_auth_failure_response(response) -> bool:
    """仅识别明确的未认证响应，不把普通业务失败或权限不足当成 Token 失效。"""
    payload = response
    if isinstance(response, dict) and isinstance(response.get("response"), dict):
        payload = response["response"]

    status_code = payload.get("status_code") if isinstance(payload, dict) else getattr(payload, "status_code", None)
    if status_code == 401:
        return True

    body = payload.get("body") if isinstance(payload, dict) else None
    if body is None and payload is not response and isinstance(payload, dict):
        body = payload.get("json")
    if body is None and not isinstance(payload, dict):
        try:
            body = payload.json()
        except Exception:
            body = None
    if not isinstance(body, dict):
        return False

    return any(body.get(key) in (401, "401") for key in ("code", "status", "error_code", "errno"))


async def execute_with_auth_retry(
    *,
    headers: dict | None,
    auth_config: dict | None,
    service: dict | None,
    token_fetcher: Callable[[dict, str], Awaitable[str | None]],
    request_func: Callable[[dict], Awaitable],
    execution_context: dict | None = None,
    auth_cache_scope: str | int | None = None,
    explicit_auth_header: bool | None = None,
    initial_resolution: AuthResolution | None = None,
) -> tuple[object, AuthResolution]:
    """发送请求；明确认证失败时重新登录并最多重试原请求一次。"""
    resolution = initial_resolution or await resolve_auth_headers(
        headers=headers,
        auth_config=auth_config,
        service=service,
        token_fetcher=token_fetcher,
        execution_context=execution_context,
        explicit_auth_header=explicit_auth_header,
        auth_cache_scope=auth_cache_scope,
    )
    result = await request_func(resolution.headers)

    # 手工 Token、显式认证头和无认证配置都不由系统自动刷新。
    if (
        not is_auth_failure_response(result)
        or not resolution.auth
        or not resolution.token
        or manual_token_from_auth(resolution.auth)
        or resolution.source == "manual_header"
    ):
        return result, resolution

    refreshed = await resolve_auth_headers(
        headers=resolution.headers,
        auth_config=auth_config,
        service=service,
        token_fetcher=token_fetcher,
        execution_context=execution_context,
        explicit_auth_header=False,
        auth_cache_scope=auth_cache_scope,
        force_refresh=True,
        stale_token=resolution.token,
    )
    retry_result = await request_func(refreshed.headers)
    return retry_result, refreshed
