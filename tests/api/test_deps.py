from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.api import deps, exceptions
from app.app.auth.domain import AccessToken
from app.app.auth.domain.tokens import InvalidToken
from app.app.files.services import NamespaceService
from app.app.files.usecases import NamespaceUseCase
from app.app.users.domain import User
from app.app.users.services import UserService
from app.app.users.usecases import UserUseCase
from app.toolkit import timezone

if TYPE_CHECKING:
    from unittest.mock import MagicMock

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
def usecases():
    return mock.MagicMock(
        namespace=mock.MagicMock(
            NamespaceUseCase,
            namespace=mock.MagicMock(NamespaceService),
        ),
        user=mock.MagicMock(
            UserUseCase,
            user_service=mock.MagicMock(UserService)
        ),
    )


class TestCurrentUser:
    @pytest.fixture
    def payload(self, user: User):
        return AccessToken(sub=str(user.id), exp=timezone.now())

    async def test(self, payload: AccessToken, usecases: MagicMock):
        # WHEN
        result = await deps.current_user(payload=payload, usecases=usecases)
        # THEN
        assert result == usecases.user.user_service.get_by_id.return_value
        usecases.user.user_service.get_by_id.assert_awaited_once_with(payload.sub)

    async def test_when_user_not_found(self, payload: AccessToken, usecases: MagicMock):
        # GIVEN
        usecases.user.user_service.get_by_id.side_effect = User.NotFound
        # WHEN/THEN
        with pytest.raises(exceptions.UserNotFound):
            await deps.current_user(payload=payload, usecases=usecases)
        usecases.user.user_service.get_by_id.assert_awaited_once_with(payload.sub)


class TestNamespace:
    async def test(self, user: User, usecases: MagicMock):
        # WHEN
        result = await deps.namespace(user=user, usecases=usecases)
        # THEN
        assert result == usecases.namespace.namespace.get_by_owner_id.return_value
        usecases.namespace.namespace.get_by_owner_id.assert_awaited_once_with(user.id)


class TestTokenPayload:
    def test(self):
        token = "token"
        with mock.patch.object(AccessToken, "decode") as decode_mock:
            result = deps.token_payload(token=token)
        assert result == decode_mock.return_value
        decode_mock.assert_called_once_with(token)

    def test_when_token_is_missing(self):
        with pytest.raises(exceptions.MissingToken):
            deps.token_payload(token=None)

    def test_when_token_is_invalid(self):
        token = "token"
        with mock.patch.object(AccessToken, "decode") as decode_mock:
            decode_mock.side_effect = InvalidToken
            with pytest.raises(exceptions.InvalidToken):
                deps.token_payload(token=token)
        decode_mock.assert_called_once_with(token)
