"""Tests for auth router endpoints."""

from fastapi import status
from fastapi.testclient import TestClient

from test_support.test_data.scenarios import DatabaseScenario


class TestTokenEndpoint:
    """Tests for POST /token."""

    def test_correct_login(self, client: TestClient, sample_scenario: DatabaseScenario):
        response = client.post("/token", data={"username": "admin", "password": "123"})
        assert response.status_code == status.HTTP_200_OK
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"

    def test_wrong_password(self, client: TestClient, sample_scenario: DatabaseScenario):
        response = client.post("/token", data={"username": "user", "password": "wrong_password"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRegisterEndpoint:
    """Tests for POST /register."""

    def test_success(self, client: TestClient, sample_scenario: DatabaseScenario):
        response = client.post("/register", json={"userName": "user2", "userPassword": "abc", "userType": "user"})
        assert response.status_code == status.HTTP_200_OK

    def test_duplicate_user(self, client: TestClient, sample_scenario: DatabaseScenario):
        response = client.post("/register", json={"userName": "user", "userPassword": "pwd", "userType": "user"})
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_admin_rejected(self, client: TestClient, sample_scenario: DatabaseScenario):
        response = client.post("/register", json={"userName": "admin2", "userPassword": "pwd", "userType": "admin"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
