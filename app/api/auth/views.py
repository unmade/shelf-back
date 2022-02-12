from __future__ import annotations

from edgedb import AsyncIOClient
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app import crud, errors, security
from app.api import deps

from . import exceptions
from .schemas import Tokens

router = APIRouter()


@router.post("/tokens", response_model=Tokens)
async def get_tokens(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db_client: AsyncIOClient = Depends(deps.db_client),
):
    """Grant new access token for a given credentials."""
    username = form_data.username.lower()
    try:
        uid, password = await crud.user.get_password(db_client, username=username)
    except errors.UserNotFound as exc:
        raise exceptions.InvalidCredentials() from exc

    if not security.verify_password(form_data.password, password):
        raise exceptions.InvalidCredentials()

    return Tokens(
        access_token=security.create_access_token(str(uid))
    )


@router.put("/tokens", response_model=Tokens)
async def refresh_token(curr_user_id: str = Depends(deps.current_user_id)):
    """Grant new access token based on current access token."""
    return Tokens(
        access_token=security.create_access_token(curr_user_id)
    )
