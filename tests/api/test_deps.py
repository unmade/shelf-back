from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock
from uuid import UUID

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
from app.config import config
from app.toolkit import timezone

if TYPE_CHECKING:
    from unittest.mock import MagicMock

pytestmark = [pytest.mark.anyio]


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


class TestCurrentUserContext:
    async def test(self, user: User):
        # GIVEN
        gen = deps.current_user_ctx(user)
        # WHEN
        result = await anext(gen)
        # THEN
        current_user = CurrentUserContext.User(id=user.id, username=user.username)
        assert result.user == current_user
        assert result._token is not None
        # anyio cleans up context vars incorrectly, so clean up manually
        with pytest.raises(StopAsyncIteration):
            await anext(gen)


class TestCurrentUser:
    async def test(self, user: User):
        # GIVEN
        current_user = CurrentUserContext.User(id=user.id, username=user.username)
        ctx = CurrentUserContext(user=current_user)
        # WHEN
        result = await deps.current_user(ctx, user=user)
        # THEN
        assert result == user


class TestNamespace:
    async def test(self, user: User, usecases: MagicMock):
        # WHEN
        result = await deps.namespace(user=user, usecases=usecases)
        # THEN
        assert result == usecases.namespace.namespace.get_by_owner_id.return_value
        usecases.namespace.namespace.get_by_owner_id.assert_awaited_once_with(user.id)


class TestServiceToken:
    async def test(self):
        service_token = uuid.uuid4().hex
        with mock.patch.object(config.auth, "service_token", service_token):
            result = await deps.service_token(token=service_token)
        assert result is None

    async def test_when_token_is_missing(self):
        with pytest.raises(exceptions.MissingToken):
            await deps.service_token(token=None)

    async def test_when_token_is_invalid(self):
        service_token = uuid.uuid4()
        with (
            mock.patch.object(config.auth, "service_token", service_token.hex),
            pytest.raises(exceptions.InvalidToken),
        ):
            await deps.service_token(token=str(service_token))


class TestTokenPayload:
    async def test(self):
        token = "token"
        with mock.patch.object(AccessToken, "decode") as decode_mock:
            result = deps.token_payload(token=token)
        assert result == decode_mock.return_value
        decode_mock.assert_called_once_with(token)

    async def test_when_token_is_missing(self):
        with pytest.raises(exceptions.MissingToken):
            deps.token_payload(token=None)

    async def test_when_token_is_invalid(self):
        token = "token"
        with mock.patch.object(AccessToken, "decode") as decode_mock:
            decode_mock.side_effect = InvalidToken
            with pytest.raises(exceptions.InvalidToken):
                deps.token_payload(token=token)
        decode_mock.assert_called_once_with(token)


class TestUseCases:
    async def test(self):
        request = mock.MagicMock(Request)
        assert await deps.usecases(request) == request.state.usecases


class TestUser:
    @pytest.fixture
    def payload(self, user: User):
        return AccessToken(sub=str(user.id), exp=timezone.now())

    async def test(self, payload: AccessToken, usecases: MagicMock, user: User):
        # GIVEN
        usecases.user.user_service.get_by_id.return_value = user
        # WHEN
        result = await deps._user(usecases, payload)
        # THEN
        assert result == user
        usecases.user.user_service.get_by_id.assert_awaited_once_with(UUID(payload.sub))

    async def test_when_user_not_found(self, payload: AccessToken, usecases: MagicMock):
        # GIVEN
        usecases.user.user_service.get_by_id.side_effect = User.NotFound
        # WHEN / THEN
        with pytest.raises(exceptions.UserNotFound):
            await deps._user(usecases, payload)
        usecases.user.user_service.get_by_id.assert_awaited_once_with(UUID(payload.sub))


class TestVerifiedUser:
    async def test(self, user: User):
        # GIVEN
        user.email_verified = True
        # WHEN
        with mock.patch.object(config.features, "verification_required", True):
            result = await deps.verified_current_user(user)
        # THEN
        assert user == result

    async def test_when_verification_disabled(self, user: User):
        # GIVEN
        user.email_verified = False
        # WHEN
        with mock.patch.object(config.features, "verification_required", False):
            result = await deps.verified_current_user(user)
        # THEN
        assert user == result

    async def test_when_unverified(self, user: User):
        # GIVEN
        user.email_verified = False
        # WHEN / THEN
        with (
            mock.patch.object(config.features, "verification_required", True),
            pytest.raises(exceptions.UnverifiedUser),
        ):
            await deps.verified_current_user(user)


class TestWorker:
    async def test(self):
        request = mock.MagicMock(Request)
        assert await deps.worker(request) == request.state.worker
