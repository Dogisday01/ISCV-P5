from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from tests.types import TokenResponseData


def test_login_and_me_endpoint(
    client: TestClient,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    """Проверяет базовый путь аутентифицированной сессии для защищенных маршрутов."""
    user = make_user("engineer1@example.com", UserRole.ENGINEER, "ChangeMe123!")

    token_pair = login_as(user.email, "ChangeMe123!")
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token_pair['access_token']}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == user.email
    assert payload["role"] == UserRole.ENGINEER.value


def test_refresh_rotates_token(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[str, UserRole, str], User],
    login_as: Callable[[str, str], TokenResponseData],
) -> None:
    """Проверяет, что ротация refresh token отзывает старый токен и выдает новый."""
    user = make_user("engineer2@example.com", UserRole.ENGINEER, "ChangeMe123!")
    token_pair = login_as(user.email, "ChangeMe123!")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_pair["refresh_token"]},
    )

    assert response.status_code == 200
    refreshed = response.json()
    assert refreshed["refresh_token"] != token_pair["refresh_token"]

    stored_tokens = db_session.query(RefreshToken).filter(RefreshToken.user_id == user.id).all()
    assert len(stored_tokens) == 2
    assert any(token.revoked_at is not None for token in stored_tokens)


def test_public_registration_route_is_not_exposed(client: TestClient) -> None:
    """Проверяет, что публичная саморегистрация не открыта во внешней поверхности атаки."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-user@example.com",
            "full_name": "New User",
            "password": "ChangeMe123!",
        },
    )

    assert response.status_code == 404
