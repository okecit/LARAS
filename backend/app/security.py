"""Hash kata sandi, token JWT, pseudonimisasi, dan peta izin berbasis peran (RBAC)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

_PBKDF2_ITER = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITER)
    return f"pbkdf2_sha256${_PBKDF2_ITER}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "usr": username, "role": role, "iat": now,
               "exp": now + timedelta(minutes=settings.token_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


# --------------------------------------------------------------------------- pseudonimisasi

def actor_hash(platform_code: str, handle: str, key: str | None = None) -> str:
    """HMAC-SHA256 dari handle ternormalisasi. Handle asli tidak disimpan."""
    k = (key or settings.pseudonym_key).encode()
    msg = f"{platform_code.lower()}:{handle.strip().lstrip('@').lower()}".encode()
    return hmac.new(k, msg, hashlib.sha256).hexdigest()


PLATFORM_PREFIX = {"tiktok": "TT", "instagram": "IG", "youtube": "YT", "x": "XX"}


def pseudonym_for(platform_code: str, a_hash: str) -> str:
    return f"{PLATFORM_PREFIX.get(platform_code, 'LN')}-{a_hash[:6].upper()}"


def external_hash(platform_code: str, external_id: str, key: str | None = None) -> str:
    k = (key or settings.pseudonym_key).encode()
    return hmac.new(k, f"ext:{platform_code}:{external_id}".encode(), hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------- RBAC

PERMISSIONS: dict[str, set[str]] = {
    "admin": {"*"},
    "peneliti_utama": {
        "view", "view_raw", "annotate", "validate", "edit_taxonomy", "manage_sources", "run_jobs",
        "import", "export", "export_raw", "approve_conclusion", "manage_project", "edit_evidence", "view_audit",
    },
    "peneliti": {"view", "view_raw", "annotate", "run_jobs", "import", "export", "edit_evidence"},
    "peninjau": {"view", "view_raw", "annotate", "validate", "approve_conclusion", "edit_evidence"},
    "pengamat": {"view"},
}

ROLE_LABELS = {
    "admin": "Administrator",
    "peneliti_utama": "Peneliti Utama",
    "peneliti": "Peneliti",
    "peninjau": "Peninjau / Anotator",
    "pengamat": "Pengamat (tanpa data mentah)",
}


def has_permission(role: str, perm: str) -> bool:
    perms = PERMISSIONS.get(role, set())
    return "*" in perms or perm in perms


def permissions_for(role: str) -> list[str]:
    perms = PERMISSIONS.get(role, set())
    if "*" in perms:
        return sorted(set().union(*[p for r, p in PERMISSIONS.items() if r != "admin"]) | {"manage_users", "view_audit"})
    return sorted(perms)
