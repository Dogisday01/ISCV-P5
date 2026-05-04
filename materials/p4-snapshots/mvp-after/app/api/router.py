from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import assets, auth, health, maintenance_requests, reports, users

api_router = APIRouter()
# СЃРѕР±РёСЂР°РµРј РјРёРЅРёРјР°Р»СЊРЅС‹Р№ РЅР°Р±РѕСЂ РјР°СЂС€СЂСѓС‚РѕРІ РґР»СЏ РІР°СЂРёР°РЅС‚Р° 2
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(
    maintenance_requests.router,
    prefix="/maintenance-requests",
    tags=["maintenance-requests"],
)
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(health.router, tags=["health"])
