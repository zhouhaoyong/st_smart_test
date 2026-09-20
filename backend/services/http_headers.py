from typing import Any


def encode_headers_for_httpx(headers: dict[str, Any] | None) -> list[tuple[bytes, bytes]]:
    """Encode headers as raw bytes so non-ASCII values can be sent by httpx."""
    encoded: list[tuple[bytes, bytes]] = []
    for key, value in (headers or {}).items():
        if value is None:
            continue
        name = str(key).strip()
        if not name:
            continue
        encoded.append((name.encode("ascii"), str(value).encode("utf-8")))
    return encoded
