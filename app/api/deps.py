from __future__ import annotations

from edgedb import AsyncIOClient
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app import crud, errors
from app.entities import Namespace, User
from app.infrastructure.provider import UseCase
from app.tokens import AccessTokenPayload, InvalidToken

from . import exceptions

__all__ = [
    "current_user",
    "current_user_id",
    "db_client",
    "superuser",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/sign_in", auto_error=False)

async def db_client(request: Request) -> AsyncIOClient:
    return request.app.state.db_client  # type: ignore[no-any-return]


def token_payload(token: str | None = Depends(reusable_oauth2)) -> AccessTokenPayload:
    """Return payload from authentication token."""
    if token is None:
        raise exceptions.MissingToken() from None

    try:
        return AccessTokenPayload.decode(token)
    except InvalidToken as exc:
        raise exceptions.InvalidToken() from exc


async def current_user_id(
    db_client: AsyncIOClient = Depends(db_client),
    payload: AccessTokenPayload = Depends(token_payload),
) -> str:
    """Get user_id from a token payload."""
    if not await crud.user.exists(db_client, user_id=payload.sub):
        raise exceptions.UserNotFound()
    return payload.sub


async def current_user(
    db_client: AsyncIOClient = Depends(db_client),
    payload: AccessTokenPayload = Depends(token_payload),
) -> User:
    """Get user from a token payload."""
    try:
        return await crud.user.get_by_id(db_client, user_id=payload.sub)
    except errors.UserNotFound as exc:
        raise exceptions.UserNotFound() from exc


async def namespace(
    db_client: AsyncIOClient = Depends(db_client),
    user_id: str = Depends(current_user_id),
) -> Namespace:
    # If namespace is not found, we should fail, so don't catch NamespaceNotFound here.
    # We should fail because the system is in the inconsistent state - user exists,
    # but doesn't have a namespace
    return await crud.namespace.get_by_owner(db_client, user_id)


async def usecases(request: Request) -> UseCase:
    return request.app.state.provider.usecase  # type: ignore[no-any-return]


async def superuser(user: User = Depends(current_user)) -> User:
    """Get superuser from a token payload."""
    if not user.superuser:
        raise exceptions.PermissionDenied()
    return user
