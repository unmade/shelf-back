from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.users.domain import User
from app.toolkit import taskgroups

if TYPE_CHECKING:
    from app.app.audit.services import AuditTrailService
    from app.app.auth.services import TokenService
    from app.app.auth.services.token import Tokens
    from app.app.files.services import NamespaceService
    from app.app.infrastructure.database import IAtomic
    from app.app.users.services import UserService

    class IUseCaseServices(IAtomic, Protocol):
        audit_trail: AuditTrailService
        namespace: NamespaceService
        token: TokenService
        user: UserService

__all__ = ["AuthUseCase"]


class AuthUseCase:
    __slots__ = [
        "_services", "audit_trail", "ns_service", "token_service", "user_service"
    ]

    def __init__(self, services: IUseCaseServices):
        self._services = services
        self.audit_trail = services.audit_trail
        self.ns_service = services.namespace
        self.token_service = services.token
        self.user_service = services.user

    async def signin(self, username: str, password: str) -> Tokens:
        try:
            user = await self.user_service.get_by_username(username)
        except User.NotFound as exc:
            raise User.InvalidCredentials() from exc
        if not user.check_password(password):
            raise User.InvalidCredentials() from None

        taskgroups.schedule(self.audit_trail.user_signed_in(user))
        return await self.token_service.create(str(user.id))

    async def signup(
        self, username: str, password: str, storage_quota: int | None
    ) -> Tokens:
        async for tx in self._services.atomic():
            async with tx:
                user = await self.user_service.create(
                    username,
                    password,
                    storage_quota=storage_quota,
                )
                await self.ns_service.create(user.username, owner_id=user.id)
                tokens = await self.token_service.create(str(user.id))
        return tokens

    async def rotate_tokens(self, refresh_token: str) -> Tokens:
        return await self.token_service.rotate(refresh_token)
