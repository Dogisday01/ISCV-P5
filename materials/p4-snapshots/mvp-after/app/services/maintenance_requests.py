from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.asset import Asset
from app.models.enums import MaintenanceStatus, UserRole
from app.models.maintenance_request import MaintenanceRequest
from app.models.user import User
from app.schemas.maintenance_request import (
    MaintenanceRequestCreate,
    MaintenanceRequestStatusUpdate,
)

# report table 7.1: parameterized database access
# data layer: use sqlalchemy and avoid raw sql from user input
ALLOWED_STATUS_TRANSITIONS: dict[MaintenanceStatus, set[MaintenanceStatus]] = {
    MaintenanceStatus.OPEN: {MaintenanceStatus.ASSIGNED, MaintenanceStatus.CANCELLED},
    MaintenanceStatus.ASSIGNED: {MaintenanceStatus.IN_PROGRESS, MaintenanceStatus.CANCELLED},
    MaintenanceStatus.IN_PROGRESS: {MaintenanceStatus.COMPLETED},
    MaintenanceStatus.COMPLETED: set(),
    MaintenanceStatus.CANCELLED: set(),
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _get_asset(session: Session, asset_id: str) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None or not asset.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


def _get_engineer(session: Session, user_id: str) -> User:
    engineer = session.get(User, user_id)
    if engineer is None or engineer.role != UserRole.ENGINEER or not engineer.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Assigned engineer is invalid",
        )
    return engineer


def create_maintenance_request(
    session: Session,
    user: User,
    payload: MaintenanceRequestCreate,
) -> MaintenanceRequest:
    # report table 4.1: main scenario flowchart
    # flowchart: create request with open status after asset check
    asset_id = str(payload.asset_id)
    _get_asset(session, asset_id)
    request = MaintenanceRequest(
        asset_id=asset_id,
        title=payload.title,
        description=payload.description,
        issue_code=payload.issue_code,
        requested_by_id=user.id,
    )
    session.add(request)
    session.flush()
    return request


def list_maintenance_requests(
    session: Session,
    user: User,
    *,
    limit: int,
    offset: int,
) -> Sequence[MaintenanceRequest]:
    # report table 2.3: trust boundary business logic to database
    # report table 7.3: data visibility rules
    # data access: supervisor and technical admin see all, engineer sees related requests
    statement: Select[tuple[MaintenanceRequest]]
    if user.role in {UserRole.TECHNICAL_ADMIN, UserRole.SUPERVISOR}:
        statement = (
            select(MaintenanceRequest)
            .order_by(MaintenanceRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        statement = (
            select(MaintenanceRequest)
            .where(
                or_(
                    MaintenanceRequest.requested_by_id == user.id,
                    MaintenanceRequest.assigned_engineer_id == user.id,
                )
            )
            .order_by(MaintenanceRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    return list(session.execute(statement).scalars().all())


def get_maintenance_request(session: Session, request_id: str) -> MaintenanceRequest:
    statement: Select[tuple[MaintenanceRequest]] = select(MaintenanceRequest).where(
        MaintenanceRequest.id == request_id
    )
    request = session.execute(statement).scalar_one_or_none()
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance request not found",
        )
    return request


def change_maintenance_status(
    session: Session,
    request: MaintenanceRequest,
    payload: MaintenanceRequestStatusUpdate,
) -> MaintenanceRequest:
    # report table 6.1: data flow analysis
    # report table 9.1: fixed issue status transition control
    # data flow: update status only after transition checks pass
    allowed_targets = ALLOWED_STATUS_TRANSITIONS[request.status]
    if payload.status not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid status transition",
        )

    if payload.status == MaintenanceStatus.ASSIGNED and payload.assigned_engineer_id is not None:
        engineer = _get_engineer(session, str(payload.assigned_engineer_id))
        request.assigned_engineer_id = engineer.id

    if payload.internal_notes is not None:
        request.internal_notes = payload.internal_notes

    request.status = payload.status
    if payload.status == MaintenanceStatus.COMPLETED:
        request.completed_at = _utcnow()
    elif payload.status == MaintenanceStatus.CANCELLED:
        request.completed_at = None

    session.flush()
    return request


def build_maintenance_summary(
    session: Session,
    *,
    limit: int,
    offset: int,
) -> tuple[int, int, int, int, Sequence[MaintenanceRequest]]:
    # report table 5.2: critical code area report export
    # report export: build summary data for the privileged report route
    # P4 hardening point: keep export bounded and avoid N+1 lookups on related assets.
    items_statement: Select[tuple[MaintenanceRequest]] = (
        select(MaintenanceRequest)
        .options(joinedload(MaintenanceRequest.asset))
        .order_by(MaintenanceRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.execute(items_statement).scalars().all())
    total_requests = session.scalar(select(func.count(MaintenanceRequest.id))) or 0
    open_requests = session.scalar(
        select(func.count(MaintenanceRequest.id)).where(
            MaintenanceRequest.status.in_(
                [MaintenanceStatus.OPEN, MaintenanceStatus.ASSIGNED]
            )
        )
    ) or 0
    completed_requests = session.scalar(
        select(func.count(MaintenanceRequest.id)).where(
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED
        )
    ) or 0
    cancelled_requests = session.scalar(
        select(func.count(MaintenanceRequest.id)).where(
            MaintenanceRequest.status == MaintenanceStatus.CANCELLED
        )
    ) or 0
    return total_requests, open_requests, completed_requests, cancelled_requests, items
