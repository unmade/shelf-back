from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest
from fastapi import Request

from app.api import deps, exceptions
from app.app.audit.domain import CurrentUserContext
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


@pytest.mark.asyncio
class TestUseCases:
    async def test(self):
        request = mock.MagicMock(Request)
        assert await deps.usecases(request) == request.state.usecases


@pytest.mark.asyncio
class TestWorker:
    async def test(self):
        request = mock.MagicMock(Request)
        assert await deps.worker(request) == request.state.worker


@pytest.mark.asyncio
class TestCurrentUserContext:
    @pytest.fixture
    def payload(self, user: User):
        return AccessToken(sub=str(user.id), exp=timezone.now())

    async def test(self, payload: AccessToken, usecases: MagicMock, user: User):
        # GIVEN
        usecases.user.user_service.get_by_id.return_value = user
        # WHEN
        result = await anext(deps.current_user_ctx(payload=payload, usecases=usecases))
        # THEN
        current_user = CurrentUserContext.User(id=user.id, username=user.username)
        assert result == CurrentUserContext(user=current_user)
        usecases.user.user_service.get_by_id.assert_awaited_once_with(payload.sub)

    async def test_when_user_not_found(self, payload: AccessToken, usecases: MagicMock):
        # GIVEN
        usecases.user.user_service.get_by_id.side_effect = User.NotFound
        # WHEN/THEN
        with pytest.raises(exceptions.UserNotFound):
            await anext(deps.current_user_ctx(payload=payload, usecases=usecases))
        usecases.user.user_service.get_by_id.assert_awaited_once_with(payload.sub)


@pytest.mark.asyncio
class TestCurrentUser:
    async def test(self, user: User):
        # GIVEN
        current_user = CurrentUserContext.User(id=user.id, username=user.username)
        ctx = CurrentUserContext(user=current_user)
        # WHEN
        result = await deps.current_user(ctx=ctx)
        # THEN
        assert result == ctx.user


@pytest.mark.asyncio
class TestNamespace:
    async def test(self, user: User, usecases: MagicMock):
        current_user = CurrentUserContext.User(id=user.id, username=user.username)
        # WHEN
        result = await deps.namespace(user=current_user, usecases=usecases)
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
