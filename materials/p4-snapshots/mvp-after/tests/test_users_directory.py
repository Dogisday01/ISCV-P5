from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole
from app.models.user import User
from tests.types import TokenResponseData


def test_supervisor_can_list_engineers_but_engineer_cannot(
    client: TestClient,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    """Проверяет ролевой доступ к списку инженеров: supervisor может, engineer нет."""
    supervisor = make_user("supervisor-directory@example.com", UserRole.SUPERVISOR, "ChangeMe123!")
    engineer = make_user("engineer-directory@example.com", UserRole.ENGINEER, "ChangeMe123!")

    supervisor_tokens = login_as(supervisor.email, "ChangeMe123!")
    supervisor_response = client.get(
        "/api/v1/users?role=engineer&limit=10",
        headers={"Authorization": f"Bearer {supervisor_tokens['access_token']}"},
    )

    assert supervisor_response.status_code == 200, supervisor_response.text
    payload = supervisor_response.json()
    assert any(item["id"] == engineer.id for item in payload)

    engineer_tokens = login_as(engineer.email, "ChangeMe123!")
    engineer_response = client.get(
        "/api/v1/users?role=engineer&limit=10",
        headers={"Authorization": f"Bearer {engineer_tokens['access_token']}"},
    )

    assert engineer_response.status_code == 403
