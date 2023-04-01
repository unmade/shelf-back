from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.users.domain import User

if TYPE_CHECKING:
    from app.app.auth.services import TokenService
    from app.app.auth.services.token import Tokens
    from app.app.files.services import NamespaceService
    from app.app.users.services import UserService

__all__ = ["AuthUseCase"]


class AuthUseCase:
    __slots__ = ["ns_service", "token_service", "user_service"]

    def __init__(
        self,
        namespace_service: NamespaceService,
        token_service: TokenService,
        user_service: UserService,
    ):
        self.ns_service = namespace_service
        self.token_service = token_service
        self.user_service = user_service

    async def signin(self, username: str, password: str) -> Tokens:
        try:
            user = await self.user_service.get_by_username(username)
        except User.NotFound as exc:
            raise User.InvalidCredentials() from exc
        if not user.check_password(password):
            raise User.InvalidCredentials() from None
        return await self.token_service.create(str(user.id))

    async def signup(
        self, username: str, password: str, storage_quota: int | None
    ) -> Tokens:
        user = await self.user_service.create(
            username,
            password,
            storage_quota=storage_quota,
        )
        await self.ns_service.create(user.username, owner_id=user.id)
        return await self.token_service.create(str(user.id))

    async def rotate_tokens(self, refresh_token: str) -> Tokens:
        return await self.token_service.rotate(refresh_token)
