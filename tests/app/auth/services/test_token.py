from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.auth.domain import RefreshToken
from app.app.auth.domain.tokens import InvalidToken, ReusedToken

if TYPE_CHECKING:
    from app.app.auth.services import TokenService

pytestmark = [pytest.mark.asyncio]


class TestCreate:
    async def test(self, token_service: TokenService):
        # GIVEN
        user_id = str(uuid.uuid4())
        repo = cast(mock.AsyncMock, token_service.token_repo)
        # WHEN
        result = await token_service.create(user_id)
        # THEN
        assert result
        repo.set.assert_awaited_once()


class TestRotate:
    async def test(self, token_service: TokenService):
        # GIVEN
        user_id = str(uuid.uuid4())
        refresh_token = RefreshToken.build(user_id)
        repo = cast(mock.AsyncMock, token_service.token_repo)
        repo.get.return_value = refresh_token.token_id
        # WHEN
        result = await token_service.rotate(refresh_token.encode())
        # THEN
        assert result
        repo.get.assert_awaited_once_with(refresh_token.family_id)
        repo.delete.assert_not_awaited()
        repo.set.assert_awaited_once_with(key=refresh_token.family_id, value=mock.ANY)

    async def test_when_token_is_expired(self, token_service: TokenService):
        # GIVEN
        user_id = str(uuid.uuid4())
        refresh_token = RefreshToken.build(user_id)
        repo = cast(mock.AsyncMock, token_service.token_repo)
        repo.get.return_value = None
        # WHEN
        with pytest.raises(InvalidToken):
            await token_service.rotate(refresh_token.encode())
        # THEN
        repo.get.assert_awaited_once_with(refresh_token.family_id)
        repo.delete.assert_not_awaited()
        repo.set.assert_not_awaited()

    async def test_when_token_reused(self, token_service: TokenService):
        # GIVEN
        user_id = str(uuid.uuid4())
        token_id = uuid.uuid4().hex
        refresh_token = RefreshToken.build(user_id)
        repo = cast(mock.AsyncMock, token_service.token_repo)
        repo.get.return_value = token_id
        # WHEN
        with pytest.raises(ReusedToken):
            await token_service.rotate(refresh_token.encode())
        repo.get.assert_awaited_once_with(refresh_token.family_id)
        repo.delete.assert_awaited_once_with(refresh_token.family_id)
        repo.set.assert_not_awaited()
