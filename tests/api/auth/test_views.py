from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.api.auth.exceptions import (
    InvalidCredentials,
    SignUpDisabled,
    UserAlreadyExists,
)
from app.api.exceptions import InvalidToken
from app.app.auth.domain.tokens import ReusedToken
from app.app.auth.services.token import Tokens
from app.app.users.domain import User
from app.config import config

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]


class TestSignIn:
    url = "/auth/sign_in"

    async def test(self, client: TestClient, auth_use_case: MagicMock):
        # GIVEN
        tokens = Tokens(access="access", refresh="refresh")
        auth_use_case.signin.return_value = tokens
        username, password = "admin", "root"
        data = {"username": username, "password": password}
        # WHEN
        response = await client.post(self.url, data=data)
        # THEN
        assert response.json()["access_token"] == tokens.access
        assert response.json()["refresh_token"] == tokens.refresh
        auth_use_case.signin.assert_awaited_once_with(username, password)

    async def test_when_credentials_are_invalid(
        self, client: TestClient, auth_use_case: MagicMock
    ):
        # GIVEN
        auth_use_case.signin.side_effect = User.InvalidCredentials
        username, password = "admin", "root"
        data = {"username": username, "password": password}
        # WHEN
        response = await client.post(self.url, data=data)
        # THEN
        assert response.json() == InvalidCredentials().as_dict()
        assert response.status_code == 401


class TestSignUp:
    url = "/auth/sign_up"

    async def test(self, client: TestClient, auth_use_case: MagicMock):
        # GIVEN
        tokens = Tokens(access="access", refresh="refresh")
        auth_use_case.signup.return_value = tokens
        payload = {
            "email": "johndoe@example.com",
            "display_name": "John Doe",
            "password": "Password1",
            "confirm_password": "Password1",
        }
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert "access_token" in response.json()
        assert response.status_code == 200
        auth_use_case.signup.assert_awaited_once_with(
            email=payload["email"],
            display_name=payload["display_name"],
            password=payload["password"],
        )

    async def test_when_disabled(self, client: TestClient, auth_use_case: MagicMock):
        # GIVEN
        payload = {
            "email": "johndoe@example.com",
            "display_name": "John Doe",
            "password": "Password1",
            "confirm_password": "Password1",
        }

        # WHEN
        with mock.patch.object(config.features, "sign_up_enabled", False):
            response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SignUpDisabled().as_dict()
        assert response.status_code == 400
        auth_use_case.signup.assert_not_awaited()

    async def test_when_user_already_exists(
        self, client: TestClient, auth_use_case: MagicMock
    ):
        # GIVEN
        payload = {
            "email": "johndoe@example.com",
            "display_name": "John Doe",
            "password": "Password1",
            "confirm_password": "Password1",
        }
        msg = "Username 'johndoe' is taken"
        auth_use_case.signup.side_effect = User.AlreadyExists(msg)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        message = str(auth_use_case.signup.side_effect)
        assert response.json() == UserAlreadyExists(message).as_dict()
        assert response.status_code == 400
        auth_use_case.signup.assert_awaited_once()


class TestRefreshToken:
    async def test(self, client: TestClient, auth_use_case: MagicMock):
        # GIVEN
        tokens = Tokens(access="access", refresh="refresh")
        auth_use_case.rotate_tokens.return_value = tokens
        refresh_token = "refresh-token"
        headers = {"x-shelf-refresh-token": refresh_token}
        # WHEN
        response = await client.post("/auth/refresh_token", headers=headers)
        # THEN
        assert response.json()["access_token"] == tokens.access
        assert response.json()["refresh_token"] == tokens.refresh
        assert response.status_code == 200
        auth_use_case.rotate_tokens.assert_awaited_once_with(refresh_token)

    async def test_when_header_is_not_provided(self, client: TestClient):
        # WHEN
        response = await client.post("/auth/refresh_token")
        # THEN
        assert response.json() == InvalidToken().as_dict()
        assert response.status_code == 403

    async def test_when_token_is_invalid(
        self, client: TestClient, auth_use_case: MagicMock
    ):
        # GIVEN
        auth_use_case.rotate_tokens.side_effect = ReusedToken
        refresh_token = "reused-token"
        headers = {"x-shelf-refresh-token": refresh_token}
        # WHEN
        response = await client.post("/auth/refresh_token", headers=headers)
        # THEN
        assert response.json() == InvalidToken().as_dict()
        assert response.status_code == 403
        auth_use_case.rotate_tokens.assert_awaited_once_with(refresh_token)
