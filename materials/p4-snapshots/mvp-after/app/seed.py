from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.asset import AssetCreate
from app.schemas.maintenance_request import MaintenanceRequestCreate
from app.schemas.user import UserCreate
from app.services.assets import create_asset
from app.services.auth import create_user, get_user_by_email
from app.services.maintenance_requests import create_maintenance_request


def ensure_user(session: Session, *, email: str, full_name: str, password: str, role: UserRole) -> User:
    user = get_user_by_email(session, email)
    if user is not None:
        return user
    payload = UserCreate(email=email, full_name=full_name, password=password)
    user = create_user(session, payload, role=role)
    session.flush()
    return user


def main() -> None:
        # report table 8.1: minimum test dataset
    # seed data: create a minimal dataset for login, asset, and request flow
    with SessionLocal() as session:
        admin = ensure_user(
            session,
            email=settings.bootstrap_admin_email,
            full_name="Technical Admin",
            password=settings.bootstrap_admin_password,
            role=UserRole.TECHNICAL_ADMIN,
        )
        supervisor = ensure_user(
            session,
            email=settings.bootstrap_staff_email,
            full_name="Supervisor User",
            password=settings.bootstrap_staff_password,
            role=UserRole.SUPERVISOR,
        )
        engineer = ensure_user(
            session,
            email=settings.bootstrap_user_email,
            full_name="Field Engineer",
            password=settings.bootstrap_user_password,
            role=UserRole.ENGINEER,
        )

        if not supervisor.registered_assets:
            asset = create_asset(
                session,
                supervisor,
                AssetCreate(
                    asset_tag="PUMP-1001",
                    name="Main transfer pump",
                    facility="Kyzylorda South Field",
                    equipment_type="Pump",
                    location_detail="Block A / Line 3",
                ),
            )
            request = create_maintenance_request(
                session,
                engineer,
                MaintenanceRequestCreate(
                    asset_id=UUID(asset.id),
                    title="Seal leakage inspection",
                    description="Visible leakage near the pump shaft seal.",
                    issue_code="LEAK-01",
                ),
            )
            request.assigned_engineer_id = engineer.id
        _ = admin
        session.commit()


if __name__ == "__main__":
    main()
