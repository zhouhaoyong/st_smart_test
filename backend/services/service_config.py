from urllib.parse import urlparse


def normalize_service_key(value: str | None) -> str | None:
    """将服务引用统一为可跨环境复用的逻辑标识。"""
    key = str(value or "").strip()
    return key or None


def _clean_path(value: str | None) -> str:
    path = str(value or "").strip()
    if not path:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or ""


def normalize_service_config(service_config: dict | None = None) -> dict:
    items = []
    seen = set()
    if isinstance(service_config, dict):
        raw_items = service_config.get("items") or []
    elif isinstance(service_config, list):
        raw_items = service_config
    else:
        raw_items = []

    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            continue
        key = normalize_service_key(raw.get("key") or raw.get("name"))
        path_prefix = _clean_path(raw.get("path_prefix") or raw.get("prefix") or raw.get("path"))
        if not key or not path_prefix or key in seen:
            continue
        seen.add(key)
        items.append({
            "key": key,
            "name": str(raw.get("name") or key).strip(),
            "path_prefix": path_prefix,
            "enabled": raw.get("enabled") is True,
            "description": str(raw.get("description") or "").strip(),
            "auth_key": str(raw.get("auth_key") or "").strip(),
            "priority": int(raw.get("priority") or index + 1),
        })

    items.sort(key=lambda item: (item["priority"], item["key"]))
    return {"enabled": any(item["enabled"] for item in items), "items": items}


def get_enabled_services(service_config: dict | None) -> list[dict]:
    normalized = normalize_service_config(service_config)
    if not normalized.get("enabled"):
        return []
    return [item for item in normalized["items"] if item.get("enabled")]


def get_service(service_config: dict | None, service_key: str | None) -> dict | None:
    key = normalize_service_key(service_key)
    if not key:
        return None
    for item in get_enabled_services(service_config):
        if item["key"] == key:
            return item
    return None


def _with_port(base_url: str, port: int | None = None) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base or not port or port in (80, 443) or "://" not in base:
        return base
    scheme, rest = base.split("://", 1)
    host_part = rest.split("/", 1)[0]
    if ":" in host_part:
        return base
    if "/" in rest:
        host, path = rest.split("/", 1)
        return f"{scheme}://{host}:{port}/{path}".rstrip("/")
    return f"{scheme}://{rest}:{port}".rstrip("/")


def join_url(base_url: str, path: str | None, port: int | None = None) -> str:
    base = _with_port(base_url, port)
    raw_path = str(path or "").strip()
    if raw_path.startswith("http://") or raw_path.startswith("https://"):
        return raw_path
    if not raw_path:
        return base
    return f"{base}/{raw_path.lstrip('/')}" if base else "/" + raw_path.lstrip("/")


def resolve_service_url(
    base_url: str,
    interface_url: str | None,
    service_config: dict | None = None,
    service_key: str | None = None,
    port: int | None = None,
) -> tuple[str, dict | None]:
    service = get_service(service_config, service_key)
    path = str(interface_url or "").strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path, service
    if service:
        prefix = service["path_prefix"]
        clean_path = _clean_path(path)
        if clean_path == prefix:
            path = ""
        elif clean_path.startswith(prefix + "/"):
            path = clean_path[len(prefix):]
        full_path = f"{prefix}/{str(path or '').lstrip('/')}".rstrip("/")
        return join_url(base_url, full_path or "/", port), service
    return join_url(base_url, path, port), None


def match_service_for_url(
    raw_url: str | None,
    base_url: str | None,
    service_config: dict | None,
) -> tuple[str | None, str | None, dict | None]:
    """Return (service_key, relative_url, service) by longest service path match."""
    url = str(raw_url or "").strip()
    if not url:
        return None, url, None

    parsed = urlparse(url)
    path = parsed.path if parsed.scheme and parsed.netloc else url
    query = f"?{parsed.query}" if parsed.query else ""

    base_path = ""
    if base_url:
        base_parsed = urlparse(str(base_url))
        base_path = _clean_path(base_parsed.path)
    clean_path = _clean_path(path)
    if base_path and clean_path.startswith(base_path + "/"):
        clean_path = clean_path[len(base_path):] or "/"
    elif base_path and clean_path == base_path:
        clean_path = "/"

    matches = []
    for service in get_enabled_services(service_config):
        prefix = service["path_prefix"]
        if clean_path == prefix or clean_path.startswith(prefix + "/"):
            matches.append((len(prefix), service))
    if not matches:
        return None, clean_path + query, None

    service = sorted(matches, key=lambda item: item[0], reverse=True)[0][1]
    relative = clean_path[len(service["path_prefix"]):] or "/"
    return service["key"], _clean_path(relative) + query, service


def service_meta(service: dict | None) -> dict | None:
    if not service:
        return None
    return {
        "key": service.get("key"),
        "name": service.get("name") or service.get("key"),
        "path_prefix": service.get("path_prefix"),
    }
