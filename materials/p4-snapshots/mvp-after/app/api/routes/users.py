from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.core.authorization import require_role
from app.core.config import settings
from app.models.enums import UserRole
from app.schemas.common import clamp_limit
from app.schemas.user import UserRead
from app.services.users import list_users

router = APIRouter()


@router.get("", response_model=list[UserRead])
def read_users(
    session: DbSession,
    current_user: CurrentUser,
    role: UserRole | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
) -> list[UserRead]:
    require_role(current_user, UserRole.SUPERVISOR, UserRole.TECHNICAL_ADMIN)
    users = list_users(
        session,
        role=role,
        limit=clamp_limit(
            limit,
            default_limit=settings.user_list_default_limit,
            max_limit=settings.user_list_max_limit,
        ),
        offset=offset,
    )
    return [UserRead.model_validate(user) for user in users]


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
