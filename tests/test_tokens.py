from __future__ import annotations

import uuid

import pytest

from app import tokens

pytestmark = [pytest.mark.asyncio]


class TestRotateTokens:
    async def test_but_token_is_expired(self) -> None:
        user_id = str(uuid.uuid4())
        refresh_token = tokens.RefreshTokenPayload.create(user_id).encode()
        with pytest.raises(tokens.InvalidToken):
            await tokens.rotate_tokens(refresh_token)

    async def test_but_token_reused(self) -> None:
        user_id = str(uuid.uuid4())
        _, refresh_token = await tokens.create_tokens(user_id)
        await tokens.rotate_tokens(refresh_token)
        with pytest.raises(tokens.ReusedToken):
            await tokens.rotate_tokens(refresh_token)
