"""Token encryption/decryption using AES-256-GCM.

Threat model: SQLite DB exfiltration. An attacker who reads the DB file should
not be able to recover Spotify OAuth tokens without the encryption key.

Uses SPOTIFY_STATS_TOKEN_KEY env var. If not set, derives from a baked-in
application secret (sufficient for single-user local app; insufficient for
multi-tenant deployments).
"""

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_SALT = b"spotify_stats_v1_salt"
_APP_SECRET = b"spotify-stats-internal-key-please-set-SPOTIFY_STATS_TOKEN_KEY"


def _derive_key() -> bytes:
    from backend.core.config import SPOTIFY_STATS_TOKEN_KEY

    secret = SPOTIFY_STATS_TOKEN_KEY.encode() if SPOTIFY_STATS_TOKEN_KEY else _APP_SECRET
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=600_000,
    )
    return kdf.derive(secret)


_KEY = _derive_key()
_GCM = AESGCM(_KEY)


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
    nonce = os.urandom(12)
    ct = _GCM.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    raw = base64.b64decode(ciphertext)
    nonce, ct = raw[:12], raw[12:]
    return _GCM.decrypt(nonce, ct, None).decode("utf-8")


def is_encrypted(value: str) -> bool:
    """Detect if a stored value is encrypted (does NOT start with '{')."""
    return not value.startswith("{")
