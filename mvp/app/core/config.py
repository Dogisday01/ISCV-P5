from __future__ import annotations

import warnings
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "P3 Universal MVP"
    environment: Literal["local", "test", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    # report table 7.5: secrets and crypto settings
    # secrets: load secret key from environment, not from source code
    secret_key: str = Field(min_length=32)
    # report table 7.2: access token lifetime
    # access token ttl: session access window in minutes
    access_token_ttl_minutes: int = 15
    # report table 7.2: refresh token lifetime
    # refresh token ttl: long-lived token window in days
    refresh_token_ttl_days: int = 7
    # report table 7.2: failed login limits
    # login lockout: max failed login attempts before lock
    login_max_attempts: int = 5
    # login lockout: temporary lock duration in minutes
    login_lockout_minutes: int = 15
    # report table 7.6: environment and least privilege
    # database settings: keep connection under a least-privilege account
    database_url: str = "sqlite:///./p3_mvp.db"
    request_body_max_bytes: int = 1024 * 1024
    cors_origins: list[AnyHttpUrl] | list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    enable_api_docs: bool = False
    trust_proxy_headers: bool = False
    bind_refresh_token_to_user_agent: bool = True
    user_agent_max_length: int = 256
    ip_address_max_length: int = 64
    asset_list_default_limit: int = 50
    asset_list_max_limit: int = 100
    request_list_default_limit: int = 50
    request_list_max_limit: int = 100
    user_list_default_limit: int = 25
    user_list_max_limit: int = 50
    report_default_limit: int = 100
    report_max_limit: int = 250
    list_max_offset: int = 10_000
    allow_public_registration: bool = False

    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = Field(min_length=12)
    bootstrap_staff_email: str = "staff@example.com"
    bootstrap_staff_password: str = Field(min_length=12)
    bootstrap_user_email: str = "user@example.com"
    bootstrap_user_password: str = Field(min_length=12)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @model_validator(mode="after")
    def validate_secrets(self) -> Settings:
        placeholder_tokens = {
            "changeme",
            "replace-me",
            "set-me",
            "example",
            "placeholder",
        }
        lowered_secret = self.secret_key.lower()
        if any(token in lowered_secret for token in placeholder_tokens):
            msg = "SECRET_KEY must be set to a real environment value."
            if self.environment == "production":
                raise ValueError(msg)
            warnings.warn(msg, stacklevel=1)
        if self.environment == "production" and self.debug:
            raise ValueError("DEBUG must be disabled in production.")
        bootstrap_passwords = (
            self.bootstrap_admin_password,
            self.bootstrap_staff_password,
            self.bootstrap_user_password,
        )
        if self.environment == "production":
            for password in bootstrap_passwords:
                lowered_password = password.lower()
                if any(token in lowered_password for token in placeholder_tokens):
                    raise ValueError(
                        "Bootstrap passwords must be real production secrets."
                    )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
