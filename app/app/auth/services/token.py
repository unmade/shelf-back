from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from app.app.auth.domain import AccessToken, RefreshToken
from app.app.auth.domain.tokens import InvalidToken, ReusedToken

if TYPE_CHECKING:
    from app.app.auth.repositories import ITokenRepository

__all__ = ["TokenService"]


class Tokens(NamedTuple):
    access: str
    refresh: str


class TokenService:
    __slots__ = ["token_repo"]

    def __init__(self, token_repo: ITokenRepository):
        self.token_repo = token_repo

    async def create(self, user_id: str) -> Tokens:
        """
        Create a new pair of an access and refresh tokens with a given user ID as
        a subject.

        Args:
            user_id (str): Identifies the subject of the JWT.

        Returns:
            Tokens: Tuple of an access and refresh tokens as JWT string.
        """
        access_token = AccessToken.build(user_id)
        refresh_token = RefreshToken.build(user_id)

        await self.token_repo.set(
            key=refresh_token.family_id,
            value=refresh_token.token_id,
        )
        return Tokens(
            access=access_token.encode(),
            refresh=refresh_token.encode(),
        )

    async def rotate(self, encoded_refresh_token: str) -> Tokens:
        """
        Grants a new pair of an access and refresh token based on the current refresh
        token.

        The refresh token will have the same `family_id` in the payload,
        but different `token_id`.

        In case given refresh token was already used, then the whole `family_id` is
        revoked.

        Args:
            refresh_token (str): Latest refresh token issued for the user.

        Raises:
            InvalidToken: If token is expired or can't be decoded.
            ReusedToken: If provided refresh token was already rotated.

        Returns:
            Tokens: Tuple of an access and refresh tokens as JWT strings.
        """
        refresh_token = RefreshToken.decode(encoded_refresh_token)
        access_token = AccessToken.build(refresh_token.sub)

        token_id = await self.token_repo.get(refresh_token.family_id)
        if token_id is None:
            raise InvalidToken() from None

        if token_id != refresh_token.token_id:
            await self.token_repo.delete(refresh_token.family_id)
            raise ReusedToken() from None

        refresh_token.rotate()

        await self.token_repo.set(
            key=refresh_token.family_id,
            value=refresh_token.token_id,
        )
        return Tokens(
            access=access_token.encode(),
            refresh=refresh_token.encode(),
        )
