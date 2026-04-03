from fastapi import status
from fastapi.testclient import TestClient

from src.auth.models import User


def test_token_endpoint_basic_correct_login(client: TestClient, sample_users: list[User]):
    response = client.post("/token", data={"username": "admin", "password": "123"})
    assert response.status_code == status.HTTP_200_OK
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_token_endpoint_basic_wrong_password(client: TestClient, sample_users: list[User]):
    response = client.post("/token", data={"username": "user", "password": "wrong_password"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_register_user_success(client: TestClient, sample_users: list[User]):
    response = client.post("/register", json={"user_name": "user2", "user_password": "abc", "user_type": "user"})
    assert response.status_code == status.HTTP_200_OK


def test_register_user_duplicate(client: TestClient, sample_users: list[User]):
    response = client.post("/register", json={"user_name": "user", "user_password": "pwd", "user_type": "user"})
    assert response.status_code == status.HTTP_409_CONFLICT


def test_register_admin(client: TestClient, sample_users: list[User]):
    response = client.post("/register", json={"user_name": "admin2", "user_password": "pwd", "user_type": "admin"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
