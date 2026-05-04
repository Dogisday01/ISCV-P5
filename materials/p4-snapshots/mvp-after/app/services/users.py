from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User


def list_users(
    session: Session,
    *,
    role: UserRole | None,
    limit: int,
    offset: int,
) -> Sequence[User]:
    statement: Select[tuple[User]] = select(User).order_by(User.full_name.asc()).offset(offset).limit(limit)
    if role is not None:
        statement = statement.where(User.role == role)
    return list(session.execute(statement).scalars().all())
