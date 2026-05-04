from __future__ import annotations

from typing import TypedDict


class TokenResponseData(TypedDict):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
