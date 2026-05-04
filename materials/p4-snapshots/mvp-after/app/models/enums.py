from __future__ import annotations

from enum import StrEnum


# report table 2.1: system roles and entities
# report table 8.1: minimum mvp roles
# roles: engineer, supervisor, and technical admin
class UserRole(StrEnum):
    TECHNICAL_ADMIN = "technical_admin"
    SUPERVISOR = "supervisor"
    ENGINEER = "engineer"


class MaintenanceStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
