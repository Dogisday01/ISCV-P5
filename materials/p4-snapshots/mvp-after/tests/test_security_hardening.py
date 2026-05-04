from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.api.deps import get_request_context
from app.main import RequestBodyLimitMiddleware
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.asset import AssetCreate
from app.schemas.maintenance_request import MaintenanceRequestCreate
from app.services.assets import create_asset
from app.services.audit import sanitize_details
from app.services.maintenance_requests import create_maintenance_request
from tests.types import TokenResponseData


def _build_request(
    *,
    headers: dict[str, str] | None = None,
    client_host: str = "10.0.0.7",
    body_messages: list[dict[str, object]] | None = None,
) -> Request:
    encoded_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    messages = iter(
        body_messages
        or [
            {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }
        ]
    )

    async def receive() -> dict[str, object]:
        return next(messages)

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": encoded_headers,
        "client": (client_host, 51123),
        "server": ("testserver", 80),
    }
    return Request(scope, receive)


@pytest.mark.anyio
async def test_request_body_limit_rejects_stream_without_content_length(monkeypatch: pytest.MonkeyPatch) -> None:
    """Регрессионный тест для обхода лимита body через поток без Content-Length."""
    monkeypatch.setattr("app.main.settings.request_body_max_bytes", 8)
    request = _build_request(
        body_messages=[
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"6789", "more_body": False},
        ]
    )

    async def call_next(inner_request: Request) -> PlainTextResponse:
        await inner_request.body()
        return PlainTextResponse("ok")

    async def noop_app(
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        _ = (scope, receive, send)

    middleware = RequestBodyLimitMiddleware(app=noop_app)
    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 413


def test_request_context_ignores_forwarded_for_when_proxy_trust_disabled() -> None:
    """Проверяет, что недоверенный X-Forwarded-For не подменяет IP в audit context."""
    request = _build_request(
        headers={
            "x-forwarded-for": "203.0.113.10, 10.10.10.10",
            "user-agent": "FieldConsole/1.0",
        }
    )

    context = get_request_context(request)

    assert context.ip_address == "10.0.0.7"


def test_audit_sanitizer_redacts_nested_secrets_and_strips_control_characters() -> None:
    """Проверяет рекурсивную очистку audit details от секретов и control characters."""
    sanitized = sanitize_details(
        {
            "meta": {
                "refresh_token": "very-secret",
                "nested": [{"authorization": "Bearer abc"}],
            },
            "note": "line-1\r\nline-2",
        }
    )

    assert sanitized == {
        "meta": {
            "refresh_token": "[REDACTED]",
            "nested": [{"authorization": "[REDACTED]"}],
        },
        "note": "line-1 line-2",
    }


def test_refresh_rejects_user_agent_mismatch(
    client: TestClient,
    make_user: Callable[[str, UserRole, str], User],
) -> None:
    """Регрессионный тест против replay refresh token из другого client context."""
    user = make_user("engineer-refresh@example.com", UserRole.ENGINEER, "ChangeMe123!")

    login_response = client.post(
        "/api/v1/auth/login",
        headers={"user-agent": "FieldConsole/1.0"},
        data={"username": user.email, "password": "ChangeMe123!"},
    )
    assert login_response.status_code == 200, login_response.text
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        headers={"user-agent": "AnotherDevice/9.9"},
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 401


def test_untrusted_host_header_is_rejected(client: TestClient) -> None:
    """Проверяет, что TrustedHostMiddleware отклоняет недоверенный Host header."""
    response = client.get("/api/v1/health", headers={"host": "evil.example"})

    assert response.status_code == 400


def test_openapi_schema_is_not_exposed_in_default_runtime(client: TestClient) -> None:
    """Проверяет, что OpenAPI schema не раскрывается в runtime по умолчанию."""
    response = client.get("/openapi.json")

    assert response.status_code == 404


def test_asset_listing_respects_limit_parameter(
    client: TestClient,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    """Регрессионный тест для ограниченного asset list после защиты от DoS."""
    supervisor = make_user("supervisor-limit-assets@example.com", UserRole.SUPERVISOR, "ChangeMe123!")
    tokens = login_as(supervisor.email, "ChangeMe123!")

    for index in range(3):
        create_response = client.post(
            "/api/v1/assets",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "asset_tag": f"PUMP-LIMIT-{index}",
                "name": f"Pump {index}",
                "facility": "South Pad",
                "equipment_type": "Pump",
                "location_detail": f"Bay {index}",
            },
        )
        assert create_response.status_code == 201, create_response.text

    response = client.get(
        "/api/v1/assets?limit=2",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_report_summary_respects_limit_parameter(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    """Регрессионный тест для ограниченного report output после availability hardening."""
    supervisor = make_user("supervisor-limit-report@example.com", UserRole.SUPERVISOR, "ChangeMe123!")
    engineer = make_user("engineer-limit-report@example.com", UserRole.ENGINEER, "ChangeMe123!")

    for index in range(3):
        asset = create_asset(
            db_session,
            supervisor,
            AssetCreate(
                asset_tag=f"VALVE-LIMIT-{index}",
                name=f"Gas Valve {index}",
                facility="North Cluster",
                equipment_type="Valve",
                location_detail=f"Rack {index}",
            ),
        )
        create_maintenance_request(
            db_session,
            engineer,
            MaintenanceRequestCreate(
                asset_id=UUID(asset.id),
                title=f"Inspection {index}",
                description="Scheduled integrity review",
                issue_code=f"CHK-{index}",
            ),
        )
    db_session.commit()

    supervisor_tokens = login_as(supervisor.email, "ChangeMe123!")
    response = client.get(
        "/api/v1/reports/maintenance-summary?limit=2",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
