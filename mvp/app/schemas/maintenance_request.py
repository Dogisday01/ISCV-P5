from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import MaintenanceStatus
from app.models.maintenance_request import MaintenanceRequest


# report table 7.1: input validation
# input validation: check asset uuid and request field lengths
class MaintenanceRequestCreate(BaseModel):
    asset_id: UUID
    title: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    issue_code: str | None = Field(default=None, min_length=2, max_length=32)


# report table 7.1: input validation
# input validation: check status update payload and engineer assignment
class MaintenanceRequestStatusUpdate(BaseModel):
    status: MaintenanceStatus
    assigned_engineer_id: UUID | None = None
    internal_notes: str | None = Field(default=None, max_length=1500)

    @model_validator(mode="after")
    def validate_assignment_requirements(self) -> MaintenanceRequestStatusUpdate:
        if self.status == MaintenanceStatus.ASSIGNED and not self.assigned_engineer_id:
            raise ValueError("assigned_engineer_id is required when assigning a request")
        if self.status != MaintenanceStatus.ASSIGNED and self.assigned_engineer_id is not None:
            raise ValueError("assigned_engineer_id can only be provided when assigning a request")
        return self


class MaintenanceRequestRead(BaseModel):
    id: str
    title: str
    description: str | None
    status: MaintenanceStatus
    issue_code: str | None
    asset_id: str
    assigned_engineer_id: str | None
    internal_notes: str | None
    completed_at: datetime | None


def serialize_maintenance_request(
    request: MaintenanceRequest,
    *,
    include_internal_notes: bool,
) -> MaintenanceRequestRead:
    # report table 7.3: service data exposure
    # service data: hide internal notes for non-privileged roles
    return MaintenanceRequestRead(
        id=request.id,
        title=request.title,
        description=request.description,
        status=request.status,
        issue_code=request.issue_code,
        asset_id=request.asset_id,
        assigned_engineer_id=request.assigned_engineer_id,
        internal_notes=request.internal_notes if include_internal_notes else None,
        completed_at=request.completed_at,
    )
