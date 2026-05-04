from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, RequestContextDep
from app.core.authorization import (
    ensure_can_transition_request,
    ensure_can_view_internal_notes,
    ensure_can_view_request,
)
from app.core.config import settings
from app.schemas.common import clamp_limit
from app.schemas.maintenance_request import (
    MaintenanceRequestCreate,
    MaintenanceRequestRead,
    MaintenanceRequestStatusUpdate,
    serialize_maintenance_request,
)
from app.services.audit import write_audit_log
from app.services.maintenance_requests import (
    change_maintenance_status,
    create_maintenance_request,
    get_maintenance_request,
    list_maintenance_requests,
)

router = APIRouter()


@router.post("", response_model=MaintenanceRequestRead, status_code=201)
def create_request(
    session: DbSession,
    current_user: CurrentUser,
    context: RequestContextDep,
    payload: MaintenanceRequestCreate,
) -> MaintenanceRequestRead:
    # report table 4.1: main scenario flowchart
    # flowchart: engineer creates a maintenance request
    request = create_maintenance_request(session, current_user, payload)
    write_audit_log(
        session,
        action="maintenance_request.create",
        outcome="success",
        context=context,
        actor_id=current_user.id,
        entity_type="maintenance_request",
        entity_id=request.id,
        details={"status": request.status.value, "asset_id": request.asset_id},
    )
    session.commit()
    session.refresh(request)
    return serialize_maintenance_request(
        request,
        include_internal_notes=ensure_can_view_internal_notes(current_user),
    )


@router.get("", response_model=list[MaintenanceRequestRead])
def read_requests(
    session: DbSession,
    current_user: CurrentUser,
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
) -> list[MaintenanceRequestRead]:
    # report table 7.3: data exposure and object visibility
    # data access: engineer sees own and assigned requests, supervisor sees all
    requests = list_maintenance_requests(
        session,
        current_user,
        limit=clamp_limit(
            limit,
            default_limit=settings.request_list_default_limit,
            max_limit=settings.request_list_max_limit,
        ),
        offset=offset,
    )
    include_internal_notes = ensure_can_view_internal_notes(current_user)
    return [
        serialize_maintenance_request(request, include_internal_notes=include_internal_notes)
        for request in requests
    ]


@router.get("/{request_id}", response_model=MaintenanceRequestRead)
def read_request(
    session: DbSession,
    current_user: CurrentUser,
    request_id: UUID,
) -> MaintenanceRequestRead:
    # report table 6.1: data flow analysis
    # report table 7.2: object-level authorization
    # object access: load request first, then check access
    request = get_maintenance_request(session, str(request_id))
    ensure_can_view_request(current_user, request)
    return serialize_maintenance_request(
        request,
        include_internal_notes=ensure_can_view_internal_notes(current_user),
    )


@router.patch("/{request_id}/status", response_model=MaintenanceRequestRead)
def update_request_status(
    session: DbSession,
    current_user: CurrentUser,
    context: RequestContextDep,
    request_id: UUID,
    payload: MaintenanceRequestStatusUpdate,
) -> MaintenanceRequestRead:
    # report table 6.1: data flow analysis
    # report table 7.2: object-level authorization
    # object access: load request first, then check access
    request = get_maintenance_request(session, str(request_id))
    # report table 4.1: main scenario flowchart
    # report table 6.1: data flow analysis
    # data flow: check role, object, and transition before database write
    ensure_can_transition_request(
        current_user,
        request,
        payload.status,
        payload.assigned_engineer_id,
        payload.internal_notes,
    )
    request = change_maintenance_status(session, request, payload)
    write_audit_log(
        session,
        action="maintenance_request.status_change",
        outcome="success",
        context=context,
        actor_id=current_user.id,
        entity_type="maintenance_request",
        entity_id=request.id,
        details={"status": request.status.value},
    )
    session.commit()
    session.refresh(request)
    return serialize_maintenance_request(
        request,
        include_internal_notes=ensure_can_view_internal_notes(current_user),
    )
