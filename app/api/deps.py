from __future__ import annotations

from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import crud, db, security
from app.entities import Account
from app.security import TokenPayload

from . import exceptions

__all__ = [
    "db_session",
    "current_account",
    "current_user_id",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/tokens", auto_error=False)

# This is just an alias to be consistent and import all deps from one place
db_session = db.get_session


def token_payload(token: Optional[str] = Depends(reusable_oauth2)) -> TokenPayload:
    if token is None:
        raise exceptions.MissingToken() from None

    try:
        return security.decode_token(token)
    except security.InvalidToken as exc:
        raise exceptions.InvalidToken() from exc


def current_user_id(
    session: Session = Depends(db_session),
    payload: TokenPayload = Depends(token_payload),
) -> int:
    user = crud.user.get_by_id(session, user_id=payload.sub)
    if not user:
        raise exceptions.UserNotFound()
    return user.id


def current_account(
    session: Session = Depends(db_session),
    payload: TokenPayload = Depends(token_payload),
) -> Account:
    if account := crud.user.get_account(session, user_id=payload.sub):
        return account
    raise exceptions.UserNotFound()
