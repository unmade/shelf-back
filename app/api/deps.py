from __future__ import annotations

from typing import Optional

from edgedb import AsyncIOConnection
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app import crud, db, security
from app.entities import User
from app.security import TokenPayload

from . import exceptions

__all__ = [
    "db_conn",
    "current_user",
    "current_user_id",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/tokens", auto_error=False)

# This is just an alias to be consistent and import all deps from one place
db_conn = db.db_conn


def token_payload(token: Optional[str] = Depends(reusable_oauth2)) -> TokenPayload:
    if token is None:
        raise exceptions.MissingToken() from None

    try:
        return security.decode_token(token)
    except security.InvalidToken as exc:
        raise exceptions.InvalidToken() from exc


async def current_user_id(
    conn: AsyncIOConnection = Depends(db_conn),
    payload: TokenPayload = Depends(token_payload),
) -> int:
    if not await crud.user.exists(conn, user_id=payload.sub):
        raise exceptions.UserNotFound()
    return payload.sub


async def current_user(
    conn: AsyncIOConnection = Depends(db_conn),
    payload: TokenPayload = Depends(token_payload),
) -> User:
    try:
        return await crud.user.get_by_id(conn, user_id=payload.sub)
    except crud.user.UserNotFound as exc:
        raise exceptions.UserNotFound() from exc
