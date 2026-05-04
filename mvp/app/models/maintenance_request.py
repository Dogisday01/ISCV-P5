from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MaintenanceStatus

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.user import User


class MaintenanceRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "maintenance_requests"

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MaintenanceStatus] = mapped_column(
        Enum(MaintenanceStatus),
        default=MaintenanceStatus.OPEN,
        nullable=False,
    )
    issue_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    requested_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assigned_engineer_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    asset: Mapped[Asset] = relationship(back_populates="maintenance_requests")
    requested_by: Mapped[User] = relationship(
        back_populates="requested_requests",
        foreign_keys=[requested_by_id],
    )
    assigned_engineer: Mapped[User | None] = relationship(
        back_populates="assigned_requests",
        foreign_keys=[assigned_engineer_id],
    )
