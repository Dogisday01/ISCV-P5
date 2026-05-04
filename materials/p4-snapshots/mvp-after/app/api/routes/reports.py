from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, RequestContextDep
from app.core.authorization import require_role
from app.core.config import settings
from app.models.enums import UserRole
from app.schemas.common import clamp_limit
from app.schemas.report import MaintenanceReportRow, MaintenanceSummaryReport
from app.services.audit import write_audit_log
from app.services.maintenance_requests import build_maintenance_summary

router = APIRouter()


@router.get("/maintenance-summary", response_model=MaintenanceSummaryReport)
def read_maintenance_summary(
    session: DbSession,
    current_user: CurrentUser,
    context: RequestContextDep,
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
) -> MaintenanceSummaryReport:
    # report table 5.2: critical code area report export
    # report table 7.2: privileged report access
    # report export: only privileged roles can access this route
    require_role(current_user, UserRole.SUPERVISOR, UserRole.TECHNICAL_ADMIN)
    total_requests, open_requests, completed_requests, cancelled_requests, items = build_maintenance_summary(
        session,
        limit=clamp_limit(
            limit,
            default_limit=settings.report_default_limit,
            max_limit=settings.report_max_limit,
        ),
        offset=offset,
    )
    rows = []
    for item in items:
        rows.append(
            MaintenanceReportRow(
                request_id=item.id,
                asset_id=item.asset_id,
                asset_tag=item.asset.asset_tag,
                title=item.title,
                status=item.status,
                assigned_engineer_id=item.assigned_engineer_id,
            )
        )

    write_audit_log(
        session,
        action="report.export",
        outcome="success",
        context=context,
        actor_id=current_user.id,
        entity_type="report",
        entity_id="maintenance-summary",
        details={"exported_rows": len(rows)},
    )
    session.commit()
    return MaintenanceSummaryReport(
        total_requests=total_requests,
        open_requests=open_requests,
        completed_requests=completed_requests,
        cancelled_requests=cancelled_requests,
        items=rows,
    )
