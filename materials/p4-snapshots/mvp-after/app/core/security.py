from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

ALGORITHM = "HS256"
# report table 7.5: cryptography
# cryptography: use argon2 and bcrypt password hashing
password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, stored_hash: str) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(plain_password, stored_hash)


def create_access_token(subject: str, role: str) -> str:
    # report table 7.2: access token lifetime
    # access token ttl: create a short-lived access token
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "typ": "access",
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("typ") != "access":
        raise InvalidTokenError("Unexpected token type")
    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def fingerprint_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
