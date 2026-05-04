from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.maintenance_request import MaintenanceRequest
    from app.models.user import User


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"

    asset_tag: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    facility: Mapped[str] = mapped_column(String(120), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    location_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    registered_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    registered_by: Mapped[User] = relationship(back_populates="registered_assets")
    maintenance_requests: Mapped[list[MaintenanceRequest]] = relationship(back_populates="asset")
