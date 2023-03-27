from __future__ import annotations

from typing import cast

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.app.files.domain import Namespace
from app.app.users.domain import User
from app.infrastructure.provider import Provider, Services, UseCases
from app.tokens import AccessTokenPayload, InvalidToken

from . import exceptions

__all__ = [
    "services",
    "usecases",
    "current_user",
    "namespace",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/sign_in", auto_error=False)


async def services(request: Request) -> Services:
    provider = cast(Provider, request.app.state.provider)
    return provider.services


async def usecases(request: Request) -> UseCases:
    provider = cast(Provider, request.app.state.provider)
    return provider.usecases


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
    services: Services = Depends(services),
) -> User:
    """Returns user from a token payload."""
    try:
        return await services.user.get_by_id(payload.sub)
    except User.NotFound as exc:
        raise exceptions.UserNotFound() from exc


async def namespace(
    user: User = Depends(current_user),
    services: Services = Depends(services),
) -> Namespace:
    """Returns a namespace for a user from a token payload."""
    # If namespace is not found, we should fail, so don't catch Namespace.NotFound here.
    # We should fail because the system is in the inconsistent state - user exists,
    # but doesn't have a namespace
    return await services.namespace.get_by_owner_id(user.id)
