from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.models.enums import MaintenanceStatus, UserRole
from app.models.maintenance_request import MaintenanceRequest
from app.models.user import User


def require_role(user: User, *allowed_roles: UserRole) -> None:
    # report table 5.2: critical code area authorization
    # report table 7.2: server-side role checks
    # authorization: base server-side role check
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


def ensure_can_register_asset(user: User) -> None:
    require_role(user, UserRole.SUPERVISOR, UserRole.TECHNICAL_ADMIN)


def ensure_can_view_request(user: User, request: MaintenanceRequest) -> None:
    # report table 7.2: object-level authorization
    # authorization: check access to this specific request
    if user.role in {UserRole.TECHNICAL_ADMIN, UserRole.SUPERVISOR}:
        return
    if request.requested_by_id == user.id or request.assigned_engineer_id == user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access to this object is forbidden",
    )


def ensure_can_view_internal_notes(user: User) -> bool:
    return user.role in {UserRole.TECHNICAL_ADMIN, UserRole.SUPERVISOR}


def ensure_can_transition_request(
    user: User,
    request: MaintenanceRequest,
    new_status: MaintenanceStatus,
    assigned_engineer_id: UUID | str | None = None,
    internal_notes: str | None = None,
) -> None:
    # report table 7.2: object-level authorization
    # authorization: check access to this specific request
    if user.role in {UserRole.TECHNICAL_ADMIN, UserRole.SUPERVISOR}:
        return

    if assigned_engineer_id is not None or internal_notes is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Status change is forbidden",
        )

    if (
        request.requested_by_id == user.id
        and new_status == MaintenanceStatus.CANCELLED
        and request.status == MaintenanceStatus.OPEN
        and request.assigned_engineer_id is None
    ):
        return

    if request.assigned_engineer_id == user.id and new_status in {
        MaintenanceStatus.IN_PROGRESS,
        MaintenanceStatus.COMPLETED,
    }:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Status change is forbidden",
    )
