from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.api.accounts import exceptions
from app.api.exceptions import APIError
from app.app.users.domain import User
from app.app.users.services.user import EmailUpdateAlreadyStarted, EmailUpdateNotStarted
from app.app.users.usecases.user import AccountSpaceUsage

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]


class TestChangeEmailComplete:
    url = "/accounts/change_email/complete"

    async def test(self, client: TestClient, user_use_case: MagicMock, user: User):
        # GIVEN
        code = "028423"
        payload = {"code": code}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        user_use_case.change_email_complete.assert_awaited_once_with(user.id, code)

    @pytest.mark.parametrize(["error", "expected_error"], [
        (EmailUpdateNotStarted(), exceptions.EmailUpdateNotStarted()),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        user_use_case: MagicMock,
        user: User,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        code = "028423"
        payload = {"code": code}
        user_use_case.change_email_complete.side_effect = error
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code
        user_use_case.change_email_complete.assert_awaited_once_with(user.id, code)


class TestChangeEmailResendCode:
    url = "/accounts/change_email/resend_code"

    async def test(self, client: TestClient, user_use_case: MagicMock, user: User):
        # GIVEN
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url)
        # THEN
        assert response.status_code == 200
        user_use_case.change_email_resend_code.assert_awaited_once_with(user.id)

    @pytest.mark.parametrize(["error", "expected_error"], [
        (EmailUpdateNotStarted(), exceptions.EmailUpdateNotStarted()),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        user_use_case: MagicMock,
        user: User,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        user_use_case.change_email_resend_code.side_effect = error
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code
        user_use_case.change_email_resend_code.assert_awaited_once_with(user.id)


class TestChangeEmailStart:
    url = "/accounts/change_email/start"

    async def test(self, client: TestClient, user_use_case: MagicMock, user: User):
        # GIVEN
        email = "johndoe@example.com"
        payload = {"email": email}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        user_use_case.change_email_start.assert_awaited_once_with(user.id, email)

    @pytest.mark.parametrize(["error", "expected_error"], [
        (User.AlreadyExists(), exceptions.EmailAlreadyTaken()),
        (EmailUpdateAlreadyStarted(), exceptions.EmailUpdateStarted() ),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        user_use_case: MagicMock,
        user: User,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        email = "johndoe@example.com"
        payload = {"email": email}
        user_use_case.change_email_start.side_effect = error
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code
        user_use_case.change_email_start.assert_awaited_once_with(user.id, email)


class TestGetCurrent:
    url = "/accounts/get_current"

    async def test(self, client: TestClient, user: User):
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        data = response.json()
        assert data["username"] == user.username
        assert data["email"] == user.email
        assert data["display_name"] == user.display_name
        assert data["verified"] is user.is_verified()
        assert data["superuser"] is user.superuser
        assert response.status_code == 200


class TestGetSpaceUsage:
    url = "/accounts/get_space_usage"

    async def test(
        self,
        client: TestClient,
        user_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        space_usage = AccountSpaceUsage(used=256, quota=1024)
        user_use_case.get_account_space_usage.return_value = space_usage
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        assert response.json() == {"quota": space_usage.quota, "used": space_usage.used}
        assert response.status_code == 200
        user_use_case.get_account_space_usage.assert_awaited_once_with(user.id)
