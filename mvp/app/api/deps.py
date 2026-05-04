from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db_session
from app.core.security import decode_access_token
from app.models.user import User
from app.services.audit import RequestContext, normalize_text

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_request_context(request: Request) -> RequestContext:
    # P4 hardening point: do not trust X-Forwarded-For unless deployment explicitly enables it.
    forwarded_for = request.headers.get("x-forwarded-for") if settings.trust_proxy_headers else None
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else None
    if ip_address is None and request.client is not None:
        ip_address = request.client.host

    return RequestContext(
        ip_address=normalize_text(ip_address, max_length=settings.ip_address_max_length),
        user_agent=normalize_text(
            request.headers.get("user-agent"),
            max_length=settings.user_agent_max_length,
        ),
    )


# report table 2.3: trust boundary client to api
# report table 7.2: bearer token validation
# access token: load current user from bearer token on protected routes
def get_current_user(
    session: Annotated[Session, Depends(get_db_session)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    user_id = str(payload.get("sub"))
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return user


DbSession = Annotated[Session, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]
