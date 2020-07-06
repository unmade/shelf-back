from __future__ import annotations

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import crud, security
from app.db import SessionLocal
from app.entities.account import Account
from app.models.user import User

from . import exceptions

__all__ = [
    "db_session",
    "current_account",
    "current_user",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/tokens")


def db_session():
    try:
        session = SessionLocal()
        yield session
    finally:
        session.close()


def current_user(
    session: Session = Depends(db_session), token: str = Depends(reusable_oauth2)
) -> User:
    try:
        token_data = security.check_token(token)
    except security.InvalidToken as exc:
        raise exceptions.InvalidToken() from exc

    user = crud.user.get(session, user_id=token_data.sub)
    if not user:
        raise exceptions.UserNotFound()
    return user


def current_account(
    session: Session = Depends(db_session), token: str = Depends(reusable_oauth2)
) -> Account:
    try:
        token_data = security.check_token(token)
    except security.InvalidToken as exc:
        raise exceptions.InvalidToken() from exc

    if account := crud.user.get_account(session, user_id=token_data.sub):
        return account
    raise exceptions.UserNotFound()
