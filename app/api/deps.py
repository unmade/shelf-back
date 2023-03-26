from __future__ import annotations

from edgedb import AsyncIOClient
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app import errors
from app.domain.entities import Namespace, User
from app.infrastructure.provider import Manager, Service, UseCase
from app.tokens import AccessTokenPayload, InvalidToken

from . import exceptions

__all__ = [
    "current_user",
    "namespace",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/sign_in", auto_error=False)


async def services(request: Request) -> Service:
    return request.app.state.provider.service  # type: ignore[no-any-return]


async def managers(request: Request) -> Manager:
    return request.app.state.provider.manager  # type: ignore[no-any-return]


async def usecases(request: Request) -> UseCase:
    return request.app.state.provider.usecase  # type: ignore[no-any-return]


async def db_client(request: Request) -> AsyncIOClient:
    return request.app.state.db_client  # type: ignore[no-any-return]


def token_payload(token: str | None = Depends(reusable_oauth2)) -> AccessTokenPayload:
    """Returns payload from authentication token."""
    if token is None:
        raise exceptions.MissingToken() from None

    try:
        return AccessTokenPayload.decode(token)
    except InvalidToken as exc:
        raise exceptions.InvalidToken() from exc


async def current_user(
    payload: AccessTokenPayload = Depends(token_payload),
    services: Service = Depends(services),
) -> User:
    """Returns user from a token payload."""
    try:
        return await services.user.get_by_id(payload.sub)
    except errors.UserNotFound as exc:
        raise exceptions.UserNotFound() from exc


async def namespace(
    user: User = Depends(current_user),
    services: Service = Depends(services),
) -> Namespace:
    """Returns a namespace for a user from a token payload."""
    # If namespace is not found, we should fail, so don't catch NamespaceNotFound here.
    # We should fail because the system is in the inconsistent state - user exists,
    # but doesn't have a namespace
    return await services.namespace.get_by_owner_id(user.id)
