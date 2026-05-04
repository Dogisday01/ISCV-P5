from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import MaintenanceStatus


class MaintenanceReportRow(BaseModel):
    request_id: str
    asset_id: str
    asset_tag: str
    title: str
    status: MaintenanceStatus
    assigned_engineer_id: str | None


class MaintenanceSummaryReport(BaseModel):
    total_requests: int
    open_requests: int
    completed_requests: int
    cancelled_requests: int
    items: list[MaintenanceReportRow]
