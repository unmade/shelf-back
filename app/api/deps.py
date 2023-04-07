from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.app.auth.domain import AccessToken, TokenError
from app.app.files.domain import Namespace
from app.app.users.domain import User
from app.infrastructure.context import UseCases

from . import exceptions

__all__ = [
    "CurrentUserDeps",
    "NamespaceDeps",
    "UseCasesDeps",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/sign_in", auto_error=False)


async def usecases(request: Request):
    return request.state.usecases


def token_payload(token: str | None = Depends(reusable_oauth2)) -> AccessToken:
    """Returns payload from authentication token."""
    if token is None:
        raise exceptions.MissingToken() from None

    try:
        return AccessToken.decode(token)
    except TokenError as exc:
        raise exceptions.InvalidToken() from exc


async def current_user(
    usecases: UseCasesDeps,
    payload: AccessToken = Depends(token_payload),
) -> User:
    """Returns user from a token payload."""
    try:
        return await usecases.user.user_service.get_by_id(payload.sub)
    except User.NotFound as exc:
        raise exceptions.UserNotFound() from exc


async def namespace(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> Namespace:
    """Returns a namespace for a user from a token payload."""
    # If namespace is not found, we should fail, so don't catch Namespace.NotFound here.
    # We should fail because the system is in the inconsistent state - user exists,
    # but doesn't have a namespace
    return await usecases.namespace.namespace.get_by_owner_id(user.id)


UseCasesDeps = Annotated[UseCases, Depends(usecases)]
CurrentUserDeps = Annotated[User, Depends(current_user)]
NamespaceDeps = Annotated[Namespace, Depends(namespace)]
