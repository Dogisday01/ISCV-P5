from __future__ import annotations

from pydantic import BaseModel


class MessageResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str = "ok"


def clamp_limit(requested_limit: int | None, *, default_limit: int, max_limit: int) -> int:
    if requested_limit is None:
        return default_limit
    return min(requested_limit, max_limit)
