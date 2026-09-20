"""
Helpers for environment and token proxy configuration.

The UI stores proxy settings as a JSON list, while older environments may still
have proxy_http/proxy_https string columns. These helpers keep both shapes usable
and select a proxy for the actual target URL at request time.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_proxy_config(
    proxy_config: dict | None = None,
    proxy_http: str | None = None,
    proxy_https: str | None = None,
) -> dict:
    items = []
    if isinstance(proxy_config, dict):
        for raw in proxy_config.get("items") or []:
            if not isinstance(raw, dict):
                continue
            is_deleted = raw.get("is_deleted", False) is True
            url = _clean(raw.get("url"))
            if not url and not is_deleted:
                continue
            scheme = str(raw.get("scheme") or raw.get("type") or "http").lower()
            if scheme not in ("http", "https"):
                scheme = "http"
            items.append({
                "name": _clean(raw.get("name")) or ("HTTP代理" if scheme == "http" else "HTTPS代理"),
                "scheme": scheme,
                "url": url or "",
                "enabled": raw.get("enabled", True) is not False,
                "priority": int(raw.get("priority") or len(items) + 1),
                "is_deleted": is_deleted,
                "deleted_at": _clean(raw.get("deleted_at")),
            })

    if not items:
        http_url = _clean(proxy_http)
        https_url = _clean(proxy_https)
        if http_url:
            items.append({"name": "HTTP代理", "scheme": "http", "url": http_url, "enabled": True, "priority": 1, "is_deleted": False, "deleted_at": None})
        if https_url:
            items.append({"name": "HTTPS代理", "scheme": "https", "url": https_url, "enabled": True, "priority": 2, "is_deleted": False, "deleted_at": None})

    return {
        "enabled": bool([item for item in items if not item.get("is_deleted")]) and (not isinstance(proxy_config, dict) or proxy_config.get("enabled", True) is not False),
        "items": sorted(items, key=lambda item: item.get("priority") or 0),
    }


def first_proxy_by_scheme(proxy_config: dict | None, scheme: str) -> str | None:
    normalized = normalize_proxy_config(proxy_config)
    if not normalized.get("enabled"):
        return None
    for item in normalized.get("items") or []:
        if item.get("is_deleted") is not True and item.get("enabled", True) is not False and item.get("scheme") == scheme:
            return item.get("url")
    return None


def select_proxy_for_url(
    target_url: str | None,
    proxy_config: dict | None = None,
    proxy_http: str | None = None,
    proxy_https: str | None = None,
) -> str | None:
    normalized = normalize_proxy_config(proxy_config, proxy_http, proxy_https)
    if not normalized.get("enabled"):
        return None

    target_scheme = (urlparse(target_url or "").scheme or "http").lower()
    items = [
        item for item in normalized.get("items") or []
        if item.get("is_deleted") is not True and item.get("enabled", True) is not False
    ]
    for item in items:
        if item.get("scheme") == target_scheme:
            return item.get("url")

    # Backward compatibility: old proxy_http was used for both HTTP and HTTPS.
    if not proxy_config and target_scheme == "https":
        return _clean(proxy_http)
    return None


def legacy_proxy_fields(proxy_config: dict | None) -> tuple[str | None, str | None]:
    normalized = normalize_proxy_config(proxy_config)
    return first_proxy_by_scheme(normalized, "http"), first_proxy_by_scheme(normalized, "https")
