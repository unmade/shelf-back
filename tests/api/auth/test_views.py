from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import config, tokens
from app.api.auth.exceptions import (
    InvalidCredentials,
    SignUpDisabled,
    UserAlreadyExists,
)
from app.api.exceptions import InvalidToken
from app.app.users.domain import User

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


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
    url = "/auth/sign_up"

    async def test(
        self, client: TestClient, ns_use_case: MagicMock, user_service: MagicMock
    ):
        # GIVEN
        payload = {
            "username": "johndoe",
            "password": "Password1",
            "confirm_password": "Password1",
        }
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert "access_token" in response.json()
        assert response.status_code == 200
        user_service.create.assert_awaited_once_with(
            payload["username"],
            payload["password"],
            storage_quota=config.STORAGE_QUOTA,
        )
        user = user_service.create.return_value
        ns_use_case.create_namespace.assert_awaited_once_with(
            user.username, owner_id=user.id
        )

    async def test_but_it_is_disabled(
        self, client: TestClient, ns_use_case: MagicMock, user_service: MagicMock
    ):
        # GIVEN
        payload = {
            "username": "johndoe",
            "password": "Password1",
            "confirm_password": "Password1",
        }

        # WHEN
        with mock.patch("app.config.FEATURES_SIGN_UP_DISABLED", True):
            response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == SignUpDisabled().as_dict()
        assert response.status_code == 400
        user_service.create.assert_not_awaited()
        ns_use_case.create_namespace.assert_not_awaited()

    async def test_but_username_is_taken(
        self, client: TestClient, ns_use_case: MagicMock, user_service: MagicMock
    ):
        # GIVEN
        payload = {
            "username": "johndoe",
            "password": "Password1",
            "confirm_password": "Password1",
        }
        msg = "Username 'johndoe' is taken"
        user_service.create.side_effect = User.AlreadyExists(msg)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        message = str(user_service.create.side_effect)
        assert response.json() == UserAlreadyExists(message).as_dict()
        assert response.status_code == 400
        user_service.create.assert_awaited_once()
        ns_use_case.create_namespace.assert_not_called()


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
