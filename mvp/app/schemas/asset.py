from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# РїСЂРѕРІРµСЂСЏРµРј С„РѕСЂРјР°С‚ Рё РґР»РёРЅСѓ РїРѕР»РµР№ Р°РєС‚РёРІР°
class AssetCreate(BaseModel):
    asset_tag: str = Field(min_length=3, max_length=40, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(min_length=3, max_length=120)
    facility: str = Field(min_length=2, max_length=120)
    equipment_type: str = Field(min_length=2, max_length=80)
    location_detail: str | None = Field(default=None, max_length=500)


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_tag: str
    name: str
    facility: str
    equipment_type: str
    location_detail: str | None
    is_active: bool
