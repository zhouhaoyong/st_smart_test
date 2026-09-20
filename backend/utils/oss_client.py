"""
OSS file storage client with strict OSS mode and local-development fallback.

Local development:
- Leave OSS_ENABLED unset and files are stored under backend/uploads/

Test/production:
- Set OSS_ENABLED=true and provide OSS_* settings to upload files to OSS
- When OSS is enabled, initialization/upload failures raise immediately instead
  of silently falling back to local disk
"""
import logging
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_oss_client = None
_oss_enabled = None
_backend_root = Path(__file__).resolve().parent.parent
_local_upload_root = _backend_root / "uploads"
SIGNED_URL_EXPIRES = 7 * 24 * 3600  # 7 days


def _is_oss_public_host(host: str) -> bool:
    return bool(re.fullmatch(r"[^.]+\.oss-[^.]+\.aliyuncs\.com", host or ""))


def _validate_oss_config(endpoint: str, bucket_name: str, prefix: str) -> None:
    """Validate the active OSS public URL config to catch bad-but-plausible URLs."""
    if not endpoint or not bucket_name:
        raise RuntimeError("OSS_ENDPOINT and OSS_BUCKET are required when OSS is enabled")

    if not prefix:
        return

    parsed = urlparse(prefix)
    host = parsed.netloc.strip()
    if not host:
        raise RuntimeError("OSS_URL_PREFIX is invalid: missing host")

    if _is_oss_public_host(host):
        expected_host = f"{bucket_name}.{endpoint}"
        if host != expected_host:
            raise RuntimeError(
                f"OSS_URL_PREFIX host '{host}' does not match OSS_BUCKET/OSS_ENDPOINT "
                f"('{expected_host}')"
            )


def _get_oss_client():
    """Lazily initialize the OSS bucket client."""
    global _oss_client, _oss_enabled
    if _oss_enabled is not None:
        return _oss_client

    _oss_enabled = os.getenv("OSS_ENABLED", "false").lower() == "true"
    if not _oss_enabled:
        logger.info("OSS is disabled, using local storage")
        return None

    try:
        import oss2

        endpoint = os.getenv("OSS_ENDPOINT", "").strip()
        bucket_name = os.getenv("OSS_BUCKET", "").strip()
        key_id = os.getenv("OSS_ACCESS_KEY_ID", "").strip()
        key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "").strip()
        prefix = os.getenv("OSS_URL_PREFIX", "").strip()

        if not all([endpoint, bucket_name, key_id, key_secret]):
            raise RuntimeError("OSS config is incomplete")

        _validate_oss_config(endpoint, bucket_name, prefix)

        auth = oss2.Auth(key_id, key_secret)
        _oss_client = oss2.Bucket(auth, endpoint, bucket_name)
        logger.info("OSS connected: bucket=%s endpoint=%s", bucket_name, endpoint)
        return _oss_client
    except Exception as exc:
        logger.error("OSS init failed: %s", exc)
        raise RuntimeError(f"OSS init failed: {exc}") from exc


def _normalize_subdir(subdir: str) -> str:
    clean = (subdir or "").strip().strip("/\\")
    if not clean or clean in {".", ".."} or "/" in clean or "\\" in clean:
        raise ValueError(f"Invalid upload subdir: {subdir!r}")
    return clean


def is_object_key(value: str | None) -> bool:
    if not value:
        return False
    return bool(re.fullmatch(r"uploads/[^/]+/[0-9a-f]{32}\.[A-Za-z0-9]+", value))


def extract_file_reference(value: str | None) -> str | None:
    """Normalize persisted file refs from old URL forms into stable object keys when possible."""
    if not value:
        return value
    if is_object_key(value) or value.startswith("/uploads/"):
        return value

    parsed = urlparse(value)
    if parsed.scheme and parsed.path.startswith("/uploads/"):
        return parsed.path.lstrip("/")
    return value


def resolve_file_url(file_ref: str | None) -> str | None:
    """Resolve a stored file reference into a browser-accessible URL."""
    if not file_ref:
        return file_ref

    normalized = extract_file_reference(file_ref)
    if not normalized:
        return normalized
    if normalized.startswith(("http://", "https://")):
        return normalized
    if normalized.startswith("uploads/"):
        oss = _get_oss_client()
        if oss:
            return oss.sign_url("GET", normalized, SIGNED_URL_EXPIRES)
        return f"/{normalized}"
    if normalized.startswith("/uploads/"):
        return normalized
    return normalized


def upload_file(
    file_data: bytes,
    subdir: str,
    filename: str = "",
    content_type: str = "image/png",
) -> str:
    """
    Upload a file and return a stable stored reference.

    For OSS storage, this returns the object key.
    For local fallback, this returns an app-relative /uploads/... path.
    """
    clean_subdir = _normalize_subdir(subdir)
    ext = os.path.splitext(filename or "img.png")[1] or ".png"
    name = f"{uuid.uuid4().hex}{ext}"
    object_key = f"uploads/{clean_subdir}/{name}"

    oss = _get_oss_client()
    if oss:
        try:
            oss.put_object(object_key, file_data, headers={"Content-Type": content_type})
            return object_key
        except Exception as exc:
            logger.error("OSS upload failed: %s", exc)
            raise RuntimeError(f"OSS upload failed: {exc}") from exc

    local_dir = _local_upload_root / clean_subdir
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / name
    local_path.write_bytes(file_data)
    return f"/uploads/{clean_subdir}/{name}"
