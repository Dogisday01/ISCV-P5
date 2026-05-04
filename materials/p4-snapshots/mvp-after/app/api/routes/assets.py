from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, RequestContextDep
from app.core.authorization import ensure_can_register_asset
from app.core.config import settings
from app.schemas.asset import AssetCreate, AssetRead
from app.schemas.common import clamp_limit
from app.services.assets import create_asset, get_asset, list_assets
from app.services.audit import write_audit_log

router = APIRouter()


@router.post("", response_model=AssetRead, status_code=201)
def create_asset_endpoint(
    session: DbSession,
    current_user: CurrentUser,
    context: RequestContextDep,
    payload: AssetCreate,
) -> AssetRead:
    # report table 4.1: main scenario flowchart
    # flowchart: supervisor registers an asset
    ensure_can_register_asset(current_user)
    asset = create_asset(session, current_user, payload)
    write_audit_log(
        session,
        action="asset.create",
        outcome="success",
        context=context,
        actor_id=current_user.id,
        entity_type="asset",
        entity_id=asset.id,
        details={"asset_tag": asset.asset_tag},
    )
    session.commit()
    session.refresh(asset)
    return AssetRead.model_validate(asset)


@router.get("", response_model=list[AssetRead])
def read_assets(
    session: DbSession,
    _: CurrentUser,
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
) -> list[AssetRead]:
    # report table 8.1: minimum mvp coverage
    # minimum mvp: authenticated asset listing
    assets = list_assets(
        session,
        limit=clamp_limit(
            limit,
            default_limit=settings.asset_list_default_limit,
            max_limit=settings.asset_list_max_limit,
        ),
        offset=offset,
    )
    return [AssetRead.model_validate(asset) for asset in assets]


@router.get("/{asset_id}", response_model=AssetRead)
def read_asset(session: DbSession, _: CurrentUser, asset_id: UUID) -> AssetRead:
    # minimum mvp: read one asset by uuid
    asset = get_asset(session, str(asset_id))
    return AssetRead.model_validate(asset)
