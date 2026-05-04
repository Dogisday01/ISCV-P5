from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.audit_log import AuditLog
    from app.models.maintenance_request import MaintenanceRequest
    from app.models.refresh_token import RefreshToken


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.ENGINEER,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    registered_assets: Mapped[list[Asset]] = relationship(back_populates="registered_by")
    requested_requests: Mapped[list[MaintenanceRequest]] = relationship(
        back_populates="requested_by",
        foreign_keys="MaintenanceRequest.requested_by_id",
    )
    assigned_requests: Mapped[list[MaintenanceRequest]] = relationship(
        back_populates="assigned_engineer",
        foreign_keys="MaintenanceRequest.assigned_engineer_id",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor")
