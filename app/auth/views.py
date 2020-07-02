from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app import config, db

from . import crud, deps, exceptions, security
from .models import User
from .schemas import Tokens

router = APIRouter()


@router.post("/tokens", response_model=Tokens)
def get_tokens(form_data: OAuth2PasswordRequestForm = Depends()):
    with db.SessionManager() as db_session:
        user = crud.get_by_username(db_session, form_data.username)

    if not user:
        raise exceptions.UserNotFound()

    if not security.verify_password(form_data.password, user.password):
        raise exceptions.UserNotFound()

    return Tokens(
        access_token=security.create_access_token(
            user.id, expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
    )


@router.put("/tokens", response_model=Tokens)
def refresh_token(curr_user: User = Depends(deps.get_current_user)):
    return Tokens(
        access_token=security.create_access_token(
            curr_user.id,
            expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    )
