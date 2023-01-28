from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import config, errors, tokens
from app.api.auth.exceptions import (
    InvalidCredentials,
    SignUpDisabled,
    UserAlreadyExists,
)
from app.api.exceptions import InvalidToken

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from fastapi import FastAPI

    from app.entities import User
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


class TestSignIn:
    url = "/auth/sign_in"

    async def test(self, client: TestClient, user: User, user_service: MagicMock):
        user_service.verify_credentials.return_value = user
        data = {
            "username": user.username,
            "password": "root",
        }
        response = await client.post(self.url, data=data)
        assert "access_token" in response.json()
        assert response.status_code == 200
        user_service.verify_credentials.assert_awaited_once_with(user.username, "root")

    async def test_when_credentials_are_invalid(
        self, client: TestClient, user_service: MagicMock
    ):
        user_service.verify_credentials.return_value = None
        data = {
            "username": "username",
            "password": "root",
        }
        response = await client.post(self.url, data=data)
        assert response.json() == InvalidCredentials().as_dict()
        assert response.status_code == 401


class TestSignUp:
    @pytest.fixture
    def signup(self, app: FastAPI):
        usecase = app.state.provider.usecase
        signup_mock = mock.AsyncMock(usecase.signup)
        with mock.patch.object(usecase, "signup", signup_mock) as mocked:
            yield mocked

    async def test(self, client: TestClient, signup: mock.AsyncMock):
        payload = {
            "username": "johndoe",
            "password": "Password1",
            "confirm_password": "Password1",
        }
        response = await client.post("/auth/sign_up", json=payload)
        assert "access_token" in response.json()
        assert response.status_code == 200
        signup.assert_awaited_once_with(
            payload["username"],
            payload["password"],
            storage_quota=config.STORAGE_QUOTA,
        )

    async def test_but_it_is_disabled(self, client: TestClient, signup: mock.AsyncMock):
        payload = {
            "username": "johndoe",
            "password": "Password1",
            "confirm_password": "Password1",
        }

        with mock.patch("app.config.FEATURES_SIGN_UP_DISABLED", True):
            response = await client.post("/auth/sign_up", json=payload)

        assert response.json() == SignUpDisabled().as_dict()
        assert response.status_code == 400
        signup.assert_not_awaited()

    async def test_but_passwords_dont_match(
        self, client: TestClient, signup: mock.AsyncMock
    ):
        payload = {
            "username": "jd",
            "password": "psswrd",
            "confirm_password": "Password1",
        }
        response = await client.post("/auth/sign_up", json=payload)
        assert response.status_code == 422
        signup.assert_not_awaited()

    async def test_but_username_is_taken(
        self, client: TestClient, signup: mock.AsyncMock
    ):
        payload = {
            "username": "johndoe",
            "password": "Password1",
            "confirm_password": "Password1",
        }
        signup.side_effect = errors.UserAlreadyExists("Username 'johndoe' is taken")
        response = await client.post("/auth/sign_up", json=payload)
        message = str(signup.side_effect)
        assert response.json() == UserAlreadyExists(message).as_dict()
        assert response.status_code == 400


class TestRefreshToken:
    async def test_refresh_token(self, client: TestClient, user: User):
        _, refresh_token = await tokens.create_tokens(str(user.id))
        headers = {"x-shelf-refresh-token": refresh_token}
        response = await client.post("/auth/refresh_token", headers=headers)
        assert "access_token" in response.json()
        assert response.status_code == 200

    async def test_refresh_token_but_header_is_not_provided(self, client: TestClient):
        response = await client.post("/auth/refresh_token")
        assert response.json() == InvalidToken().as_dict()
        assert response.status_code == 403

    async def test_refresh_token_but_token_is_invalid(self, client: TestClient):
        headers = {"x-shelf-refresh-token": "invalid_token"}
        response = await client.post("/auth/refresh_token", headers=headers)
        assert response.json() == InvalidToken().as_dict()
        assert response.status_code == 403
