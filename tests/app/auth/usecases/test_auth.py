from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.users.domain import User
from app.config import config

if TYPE_CHECKING:
    from app.app.auth.usecases import AuthUseCase

pytestmark = [pytest.mark.anyio]


class TestSignIn:
    async def test(self, auth_use_case: AuthUseCase):
        # GIVEN
        username, password = "admin", "root"
        audit_trail = cast(mock.MagicMock, auth_use_case.audit_trail)
        token_service = cast(mock.MagicMock, auth_use_case.token_service)
        user_service = cast(mock.MagicMock, auth_use_case.user_service)
        user = user_service.signin.return_value
        user.check_password = mock.Mock(return_value=True)
        # WHEN
        result = await auth_use_case.signin(username, password)
        # THEN
        assert result == token_service.create.return_value
        user_service.signin.assert_awaited_once_with(username, password)
        audit_trail.user_signed_in.assert_called_once_with(user)
        token_service.create.assert_awaited_once_with(str(user.id))

    async def test_when_user_not_found(self, auth_use_case: AuthUseCase):
        # GIVEN
        username, password = "admin", "root"
        audit_trail = cast(mock.MagicMock, auth_use_case.audit_trail)
        token_service = cast(mock.MagicMock, auth_use_case.token_service)
        user_service = cast(mock.MagicMock, auth_use_case.user_service)
        user_service.signin.side_effect = User.NotFound()
        # WHEN
        with pytest.raises(User.InvalidCredentials):
            await auth_use_case.signin(username, password)
        # THEN
        user_service.signin.assert_awaited_once_with(username, password)
        audit_trail.user_signed_in.assert_not_called()
        token_service.create.assert_not_awaited()


class TestSignUp:
    async def test(self, auth_use_case: AuthUseCase):
        # GIVEN
        email, password, display_name = "admin@example.com", "password", "Admin"
        ns_service = cast(mock.MagicMock, auth_use_case.ns_service)
        token_service = cast(mock.MagicMock, auth_use_case.token_service)
        user_service = cast(mock.MagicMock, auth_use_case.user_service)
        # WHEN
        result = await auth_use_case.signup(email, password, display_name)
        # THEN
        assert result == token_service.create.return_value
        user_service.create.assert_awaited_once_with(
            email,
            password,
            email=email,
            display_name=display_name,
            storage_quota=config.storage.quota,
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
