from __future__ import annotations

from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.user import User
from app.schemas.asset import AssetCreate


def create_asset(session: Session, user: User, payload: AssetCreate) -> Asset:
    existing = session.execute(select(Asset).where(Asset.asset_tag == payload.asset_tag.upper())).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Asset tag already exists")

    asset = Asset(
        asset_tag=payload.asset_tag.upper(),
        name=payload.name,
        facility=payload.facility,
        equipment_type=payload.equipment_type,
        location_detail=payload.location_detail,
        registered_by_id=user.id,
    )
    session.add(asset)
    session.flush()
    return asset


def list_assets(session: Session, *, limit: int, offset: int) -> Sequence[Asset]:
    statement: Select[tuple[Asset]] = (
        select(Asset).order_by(Asset.created_at.desc()).offset(offset).limit(limit)
    )
    return list(session.execute(statement).scalars().all())


def get_asset(session: Session, asset_id: str) -> Asset:
    statement: Select[tuple[Asset]] = select(Asset).where(Asset.id == asset_id)
    asset = session.execute(statement).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset
