from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import db

from . import crud, security
from .models import User

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/tokens")


def get_current_user(
    session: Session = Depends(db.get_session), token: str = Depends(reusable_oauth2)
) -> User:
    try:
        token_data = security.check_token(token)
    except security.InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from exc

    user = crud.get_by_id(session, id=token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found",
        )
    return user
