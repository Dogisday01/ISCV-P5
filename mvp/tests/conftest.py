from __future__ import annotations

from collections.abc import Callable, Generator
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db_session
from app.main import app
from app.models.base import Base
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.auth import create_user
from tests.types import TokenResponseData


@pytest.fixture()
def db_session() -> Generator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    Base.metadata.create_all(engine)

    with testing_session_local() as session:
        yield session

    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient]:
    def override_get_db_session() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_session: Session) -> Callable[[str, UserRole, str], User]:
    def _make_user(
        email: str,
        role: UserRole = UserRole.ENGINEER,
        password: str = "ChangeMe123!",
    ) -> User:
        user = create_user(
            db_session,
            UserCreate(
                email=email,
                full_name=f"{role.value.title()} User",
                password=password,
            ),
            role=role,
        )
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make_user


@pytest.fixture()
def login_as(client: TestClient) -> Callable[[str, str], TokenResponseData]:
    def _login(email: str, password: str = "ChangeMe123!") -> TokenResponseData:
        response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert response.status_code == 200, response.text
        return cast(TokenResponseData, response.json())

    return _login
