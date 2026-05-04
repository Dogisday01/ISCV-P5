from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import Select, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    fingerprint_token,
    generate_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPairResponse
from app.schemas.user import UserCreate
from app.services.audit import RequestContext, write_audit_log

# Public dummy hash used only to equalize login timing for missing or locked accounts.
DUMMY_AUTH_HASH = "$argon2id$v=19$m=65536,t=3,p=4$FjLdMEblsvy0koytNJf+WQ$KKNE5eKwk6q0zb713/euHNDHY6ctI2qMgxslS40owNI"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_user_by_email(session: Session, email: str) -> User | None:
    statement: Select[tuple[User]] = select(User).where(User.email == email.lower())
    return session.execute(statement).scalar_one_or_none()


def create_user(
    session: Session, payload: UserCreate, role: UserRole = UserRole.ENGINEER
) -> User:
    # report table 7.5: password hashing
    # cryptography: hash the password before saving the user
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        role=role,
    )
    session.add(user)
    session.flush()
    return user


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    # report table 7.2: authentication and login lockout
    # authentication: verify password and limit failed login attempts
    user = get_user_by_email(session, email)
    if user is None or not user.is_active:
        verify_password(password, DUMMY_AUTH_HASH)
        return None

    now = _utcnow()
    locked_until = _normalize_utc(user.locked_until)
    if locked_until is not None and locked_until > now:
        verify_password(password, DUMMY_AUTH_HASH)
        return None

    is_valid, updated_hash = verify_password(password, user.password_hash)
    if not is_valid:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_attempts = 0
        session.flush()
        return None

    if updated_hash is not None:
        user.password_hash = updated_hash

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    session.flush()
    return user


def build_token_pair(
    session: Session, user: User, context: RequestContext
) -> TokenPairResponse:
    # report table 6.1: data flow analysis
    # report table 7.2: token issuance and refresh storage
    # authentication: issue access token and store refresh token in the database
    refresh_token = generate_refresh_token()
    expires_at = _utcnow() + timedelta(days=settings.refresh_token_ttl_days)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=fingerprint_token(refresh_token),
            expires_at=expires_at,
            created_by_ip=context.ip_address,
            user_agent=context.user_agent,
        )
    )
    session.flush()

    access_token = create_access_token(subject=user.id, role=user.role.value)
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


def _get_refresh_token_record(
    session: Session, raw_refresh_token: str
) -> RefreshToken | None:
    statement: Select[tuple[RefreshToken]] = select(RefreshToken).where(
        RefreshToken.token_hash == fingerprint_token(raw_refresh_token)
    )
    return session.execute(statement).scalar_one_or_none()


def rotate_refresh_token(
    session: Session,
    raw_refresh_token: str,
    context: RequestContext,
) -> TokenPairResponse:
    # report table 7.2: refresh token rotation
    # authentication: rotate session only for a valid refresh token
    token_record = _get_refresh_token_record(session, raw_refresh_token)
    now = _utcnow()

    expires_at = (
        _normalize_utc(token_record.expires_at) if token_record is not None else None
    )
    revoked_at = (
        _normalize_utc(token_record.revoked_at) if token_record is not None else None
    )

    if (
        token_record is None
        or revoked_at is not None
        or expires_at is None
        or expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user = token_record.user
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if (
        settings.bind_refresh_token_to_user_agent
        and token_record.user_agent is not None
        and token_record.user_agent != context.user_agent
    ):
        # P4 hardening point: a stolen refresh token should not rotate cleanly from a different client.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    revoke_statement = (
        # P4 hardening point: revoke the token atomically so concurrent refresh calls cannot both win.
        update(RefreshToken)
        .where(
            RefreshToken.id == token_record.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now, last_used_at=now)
        .execution_options(synchronize_session=False)
    )
    revoked_result = cast(CursorResult[Any], session.execute(revoke_statement))
    if revoked_result.rowcount != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    return build_token_pair(session, user, context)


def revoke_refresh_token(session: Session, raw_refresh_token: str) -> None:
    token_record = _get_refresh_token_record(session, raw_refresh_token)
    if token_record is None or token_record.revoked_at is not None:
        return
    token_record.revoked_at = _utcnow()
    session.flush()


def register_public_user(session: Session, payload: UserCreate) -> User:
    if not settings.allow_public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )
    if get_user_by_email(session, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )
    return create_user(session, payload, role=UserRole.ENGINEER)


def record_login_success(session: Session, user: User, context: RequestContext) -> None:
    write_audit_log(
        session,
        action="auth.login",
        outcome="success",
        context=context,
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        details={"role": user.role.value},
    )


def record_login_failure(session: Session, context: RequestContext) -> None:
    write_audit_log(
        session,
        action="auth.login",
        outcome="failure",
        context=context,
    )
