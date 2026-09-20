"""Encryption utilities using Fernet (AES-128-CBC + HMAC).

Maintains backward-compatible fallback for legacy XOR-encrypted values —
old ciphertexts are decrypted once then re-encrypted with Fernet on next write.
"""
import base64
import logging
from hashlib import sha256

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte URL-safe base64 Fernet key from a secret string."""
    return base64.urlsafe_b64encode(sha256(secret.encode()).digest())


def _get_fernet(secret: str) -> Fernet:
    return Fernet(_derive_fernet_key(secret))


def encrypt(plain: str, secret: str) -> str:
    """Encrypt a plaintext string with Fernet (authenticated AES-CBC)."""
    return _get_fernet(secret).encrypt(plain.encode()).decode()


def decrypt(cipher: str, secret: str) -> str:
    """Decrypt a Fernet ciphertext. Falls back to legacy XOR for old data."""
    try:
        return _get_fernet(secret).decrypt(cipher.encode()).decode()
    except Exception:
        return _decrypt_legacy_xor(cipher, secret)


def _decrypt_legacy_xor(cipher: str, secret: str) -> str:
    """Legacy XOR 'decryption' for data stored before the Fernet migration."""
    key = sha256(secret.encode()).digest()
    cipher_bytes = base64.urlsafe_b64decode(cipher)
    result = bytes(c ^ key[i % len(key)] for i, c in enumerate(cipher_bytes))
    return result.decode()
