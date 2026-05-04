from __future__ import annotations

from fastapi.testclient import TestClient


def test_frontend_shell_is_served(client: TestClient) -> None:
    """Проверяет, что frontend-оболочка доступна после усиления backend-защиты."""
    response = client.get("/app/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Field Operations Console" in response.text


def test_frontend_script_avoids_unsafe_dom_sinks_and_persistent_token_storage(
    client: TestClient,
) -> None:
    """Проверяет XSS и хранение токенов: нет unsafe DOM sinks и persistent storage."""
    response = client.get("/app/app.js")

    assert response.status_code == 200
    assert "innerHTML" not in response.text
    assert "dangerouslySetInnerHTML" not in response.text
    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text
