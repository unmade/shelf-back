from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app import config, db

from . import crud, security
from .schemas import Tokens

router = APIRouter()


class UserNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail={"code": "USER_NOT_FOUND"})


@router.post("/tokens", response_model=Tokens)
def get_tokens(form_data: OAuth2PasswordRequestForm = Depends()):
    with db.SessionManager() as db_session:
        user = crud.get_by_username(db_session, form_data.username)

    if not user:
        raise UserNotFound()

    if not security.verify_password(form_data.password, user.password):
        raise UserNotFound()

    return Tokens(
        access_token=security.create_access_token(
            user.id, expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
    )
