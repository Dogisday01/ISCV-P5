from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DbSession, RequestContextDep
from app.schemas.auth import LogoutRequest, RefreshRequest, TokenPairResponse
from app.schemas.common import MessageResponse
from app.services.auth import (
    authenticate_user,
    build_token_pair,
    record_login_failure,
    record_login_success,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter()


@router.post("/login", response_model=TokenPairResponse)
def login_for_tokens(
    session: DbSession,
    context: RequestContextDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenPairResponse:
    # report table 5.1: critical code area authentication
    # report table 7.2: authentication and session handling
    # authentication: login and issue token pair
    user = authenticate_user(session, form_data.username, form_data.password)
    if user is None:
        record_login_failure(session, context)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or account temporarily locked",
        )

    record_login_success(session, user, context)
    token_pair = build_token_pair(session, user, context)
    session.commit()
    return token_pair


@router.post("/refresh", response_model=TokenPairResponse)
def refresh_token(
    session: DbSession,
    context: RequestContextDep,
    payload: RefreshRequest,
) -> TokenPairResponse:
    # report table 7.2: authentication and session handling
    # authentication: refresh session with refresh token
    token_pair = rotate_refresh_token(
        session,
        payload.refresh_token,
        context,
    )
    session.commit()
    return token_pair


@router.post("/logout", response_model=MessageResponse)
def logout(
    session: DbSession,
    payload: LogoutRequest,
) -> MessageResponse:
    # report table 7.2: authentication and session handling
    # authentication: close session and revoke refresh token
    revoke_refresh_token(session, payload.refresh_token)
    session.commit()
    return MessageResponse(detail="Logged out")
