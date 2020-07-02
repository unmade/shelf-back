from __future__ import annotations

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import db
from app.users import crud as users_crud
from app.users.models import User

from . import exceptions, security

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/tokens")


def get_current_user(
    session: Session = Depends(db.get_session), token: str = Depends(reusable_oauth2)
) -> User:
    try:
        token_data = security.check_token(token)
    except security.InvalidToken as exc:
        raise exceptions.InvalidToken() from exc

    user = users_crud.get_by_id(session, id=token_data.sub)
    if not user:
        raise exceptions.UserNotFound()
    return user
