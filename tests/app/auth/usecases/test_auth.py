from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.auth.usecases.auth import InvalidCredentials
from app.app.users.domain.user import User

if TYPE_CHECKING:
    from app.app.auth.usecases import AuthUseCase

pytestmark = [pytest.mark.asyncio]


class TestSignIn:
    async def test(self, auth_use_case: AuthUseCase):
        # GIVEN
        username, password = "admin", "root"
        token_service = cast(mock.MagicMock, auth_use_case.token_service)
        user_service = cast(mock.MagicMock, auth_use_case.user_service)
        user = user_service.get_by_username.return_value
        user.check_password = mock.Mock(return_value=True)
        # WHEN
        result = await auth_use_case.signin(username, password)
        # THEN
        assert result == token_service.create.return_value
        user_service.get_by_username.assert_awaited_once_with(username)
        token_service.create.assert_awaited_once_with(str(user.id))

    async def test_when_user_not_found(self, auth_use_case: AuthUseCase):
        # GIVEN
        username, password = "admin", "root"
        token_service = cast(mock.MagicMock, auth_use_case.token_service)
        user_service = cast(mock.MagicMock, auth_use_case.user_service)
        user_service.get_by_username.side_effect = User.NotFound
        # WHEN
        with pytest.raises(InvalidCredentials):
            await auth_use_case.signin(username, password)
        # THEN
        user_service.get_by_username.assert_awaited_once_with(username)
        token_service.create.assert_not_awaited()

    async def test_when_password_not_match(self, auth_use_case: AuthUseCase):
        # GIVEN
        username, password = "admin", "root"
        token_service = cast(mock.MagicMock, auth_use_case.token_service)
        user_service = cast(mock.MagicMock, auth_use_case.user_service)
        user = user_service.get_by_username.return_value
        user.check_password = mock.Mock(return_value=False)
        # WHEN
        with pytest.raises(InvalidCredentials):
            await auth_use_case.signin(username, password)
        # THEN
        user_service.get_by_username.assert_awaited_once_with(username)
        user.check_password.assert_called_once_with(password)
        token_service.create.assert_not_awaited()


class TestSignUp:
    async def test(self, auth_use_case: AuthUseCase):
        # GIVEN
        username, password, storage_quota = "admin", "password", 1024
        ns_service = cast(mock.MagicMock, auth_use_case.ns_service)
        token_service = cast(mock.MagicMock, auth_use_case.token_service)
        user_service = cast(mock.MagicMock, auth_use_case.user_service)
        # WHEN
        result = await auth_use_case.signup(username, password, storage_quota)
        # THEN
        assert result == token_service.create.return_value
        user_service.create.assert_awaited_once_with(
            username, password, storage_quota=storage_quota
        )
        user = user_service.create.return_value
        ns_service.create.assert_awaited_once_with(user.username, owner_id=user.id)
        token_service.create.assert_awaited_once_with(str(user.id))


class TestRotateTokens:
    async def test(self, auth_use_case: AuthUseCase):
        # GIVEN
        refresh_token = "refresh-token"
        token_service = cast(mock.MagicMock, auth_use_case.token_service)
        # WHEN
        result = await auth_use_case.rotate_tokens(refresh_token)
        # THEN
        assert result == token_service.rotate.return_value
        token_service.rotate.assert_awaited_once_with(refresh_token)
