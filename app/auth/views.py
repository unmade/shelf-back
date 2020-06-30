from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app import config, db

from . import crud, exceptions, security
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
        access=security.create_access_token(
            user.id, expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
    )
