from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import timezone
from app.api import deps, exceptions
from app.app.services import NamespaceService, UserService
from app.app.users.domain import User
from app.tokens import AccessTokenPayload, InvalidToken

if TYPE_CHECKING:
    from unittest.mock import MagicMock

pytestmark = [pytest.mark.asyncio]


class TestCurrentUser:
    @pytest.fixture
    def payload(self, user: User):
        return AccessTokenPayload(sub=str(user.id), exp=timezone.now())

    @pytest.fixture
    def services(self):
        return mock.MagicMock(user=mock.MagicMock(UserService))

    async def test(self, payload: AccessTokenPayload, services: MagicMock):
        # WHEN
        result = await deps.current_user(payload=payload, services=services)
        # THEN
        assert result == services.user.get_by_id.return_value
        services.user.get_by_id.assert_awaited_once_with(payload.sub)

    async def test_when_user_not_found(
        self, payload: AccessTokenPayload, services: MagicMock
    ):
        # GIVEN
        services.user.get_by_id.side_effect = User.NotFound
        # WHEN/THEN
        with pytest.raises(exceptions.UserNotFound):
            await deps.current_user(payload=payload, services=services)
        services.user.get_by_id.assert_awaited_once_with(payload.sub)


class TestNamespace:
    @pytest.fixture
    def services(self):
        return mock.MagicMock(namespace=mock.MagicMock(NamespaceService))

    async def test(self, user: User, services: MagicMock):
        # WHEN
        result = await deps.namespace(user=user, services=services)
        # THEN
        assert result == services.namespace.get_by_owner_id.return_value
        services.namespace.get_by_owner_id.assert_awaited_once_with(user.id)


class TestTokenPayload:
    def test(self):
        token = "token"
        with mock.patch.object(AccessTokenPayload, "decode") as decode_mock:
            result = deps.token_payload(token=token)
        assert result == decode_mock.return_value
        decode_mock.assert_called_once_with(token)

    def test_when_token_is_missing(self):
        with pytest.raises(exceptions.MissingToken):
            deps.token_payload(token=None)

    def test_when_token_is_invalid(self):
        token = "token"
        with mock.patch.object(AccessTokenPayload, "decode") as decode_mock:
            decode_mock.side_effect = InvalidToken
            with pytest.raises(exceptions.InvalidToken):
                deps.token_payload(token=token)
        decode_mock.assert_called_once_with(token)
