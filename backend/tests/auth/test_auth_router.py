"""Tests for auth router endpoints."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.auth.models import User
from tests.gate_logging import log_gate


class TestTokenEndpoint:
    """Tests for POST /token."""

    @pytest.mark.dependency(name="auth::router::correct_login", scope="session")
    def test_correct_login(self, client: TestClient, sample_users: list[User]):
        response = client.post("/token", data={"username": "admin", "password": "123"})
        assert response.status_code == status.HTTP_200_OK
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"

    @pytest.mark.dependency(name="auth::router::wrong_password", scope="session")
    def test_wrong_password(self, client: TestClient, sample_users: list[User]):
        response = client.post("/token", data={"username": "user", "password": "wrong_password"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.dependency(
        name="gate::auth::router::token_endpoint",
        depends=[
            "auth::router::correct_login",
            "auth::router::wrong_password",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestRegisterEndpoint:
    """Tests for POST /register."""

    @pytest.mark.dependency(name="auth::router::register_success", scope="session")
    def test_success(self, client: TestClient, sample_users: list[User]):
        response = client.post("/register", json={"userName": "user2", "userPassword": "abc", "userType": "user"})
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.dependency(name="auth::router::register_duplicate", scope="session")
    def test_duplicate_user(self, client: TestClient, sample_users: list[User]):
        response = client.post("/register", json={"userName": "user", "userPassword": "pwd", "userType": "user"})
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.dependency(name="auth::router::register_admin_rejected", scope="session")
    def test_register_admin_rejected(self, client: TestClient, sample_users: list[User]):
        response = client.post("/register", json={"userName": "admin2", "userPassword": "pwd", "userType": "admin"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.dependency(
        name="gate::auth::router::register_endpoint",
        depends=[
            "auth::router::register_success",
            "auth::router::register_duplicate",
            "auth::router::register_admin_rejected",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::auth::router",
    depends=[
        "gate::auth::router::token_endpoint",
        "gate::auth::router::register_endpoint",
    ],
    scope="session",
)
def test_gate():
    """All auth router tests must pass before downstream layers run."""
    log_gate("gate::auth::router")
