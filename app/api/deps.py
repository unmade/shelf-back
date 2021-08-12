from __future__ import annotations

from typing import Optional

from edgedb import AsyncIOPool
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app import crud, db, errors, security
from app.entities import Namespace, User
from app.security import TokenPayload

from . import exceptions

__all__ = [
    "db_pool",
    "current_user",
    "current_user_id",
    "superuser",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/tokens", auto_error=False)

# This is just an alias to be consistent and import all deps from one place
db_pool = db.db_pool


def token_payload(token: Optional[str] = Depends(reusable_oauth2)) -> TokenPayload:
    """Return payload from authentication token."""
    if token is None:
        raise exceptions.MissingToken() from None

    try:
        return security.decode_token(token)
    except security.InvalidToken as exc:
        raise exceptions.InvalidToken() from exc


async def current_user_id(
    pool: AsyncIOPool = Depends(db_pool),
    payload: TokenPayload = Depends(token_payload),
) -> str:
    """Get user_id from a token payload."""
    if not await crud.user.exists(pool, user_id=payload.sub):
        raise exceptions.UserNotFound()
    return payload.sub


async def current_user(
    pool: AsyncIOPool = Depends(db_pool),
    payload: TokenPayload = Depends(token_payload),
) -> User:
    """Get user from a token payload."""
    try:
        return await crud.user.get_by_id(pool, user_id=payload.sub)
    except errors.UserNotFound as exc:
        raise exceptions.UserNotFound() from exc


async def namespace(
    pool: AsyncIOPool = Depends(db_pool),
    user_id: str = Depends(current_user_id),
) -> Namespace:
    # if namespace is not found, we should fail, so don't catch NamespaceNotFound here.
    return await crud.namespace.get_by_owner(pool, user_id)


async def superuser(user: User = Depends(current_user)) -> User:
    """Get superuser from a token payload."""
    if not user.superuser:
        raise exceptions.PermissionDenied()
    return user
