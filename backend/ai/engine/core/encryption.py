"""
Symmetric encryption for sensitive data stored in Pulse's SQLite database.
Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
The encryption key is derived from PULSE_SECRET_KEY via PBKDF2.
"""
import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("pulse.core.encryption")

_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazily create a Fernet instance from PULSE_SECRET_KEY."""
    global _fernet_instance
    if _fernet_instance is None:
        from ai.engine.core.config import get_settings
        settings = get_settings()
        # Derive a 32-byte key from the secret using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"pulse-token-encryption-salt",
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(settings.PULSE_SECRET_KEY.encode()))
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string and return the base64-encoded ciphertext."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded Fernet token back to plaintext."""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.warning("Failed to decrypt value — returning empty string (key may have changed)")
        return ""
