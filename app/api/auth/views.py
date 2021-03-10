from __future__ import annotations

from edgedb import AsyncIOPool
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app import crud, errors, security
from app.api import deps
from app.entities import User

from . import exceptions
from .schemas import Tokens, UserMe

router = APIRouter()


@router.get("/me", response_model=UserMe)
async def get_me(user: User = Depends(deps.current_user)):
    """Returns account information for a current user."""
    return user


@router.post("/tokens", response_model=Tokens)
async def get_tokens(
    form_data: OAuth2PasswordRequestForm = Depends(),
    pool: AsyncIOPool = Depends(deps.db_pool),
):
    """Returns new access token for a given credentials."""
    try:
        uid, password = await crud.user.get_password(pool, username=form_data.username)
    except errors.UserNotFound as exc:
        raise exceptions.InvalidCredentials() from exc

    if not security.verify_password(form_data.password, password):
        raise exceptions.InvalidCredentials()

    return Tokens(
        access_token=security.create_access_token(str(uid))
    )


@router.put("/tokens", response_model=Tokens)
async def refresh_token(curr_user_id: str = Depends(deps.current_user_id)):
    """Returns new access token based on current access token."""
    return Tokens(
        access_token=security.create_access_token(curr_user_id)
    )
