from __future__ import annotations

from edgedb import AsyncIOClient
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app import actions, config, crud, errors, security
from app.api import deps

from . import exceptions
from .schemas import SignUpRequest, Tokens

router = APIRouter()


@router.post("/sign_in", response_model=Tokens)
async def sign_in(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db_client: AsyncIOClient = Depends(deps.db_client),
):
    """Grant new access token for a given credentials."""

    username = form_data.username.lower().strip()
    try:
        user_id, password = await crud.user.get_password(db_client, username=username)
    except errors.UserNotFound as exc:
        raise exceptions.InvalidCredentials() from exc

    if not security.verify_password(form_data.password, password):
        raise exceptions.InvalidCredentials()

    return Tokens(
        access_token=security.create_access_token(str(user_id))
    )


@router.post("/sign_up", response_model=Tokens)
async def sign_up(
    payload: SignUpRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
):
    """Create a new account with given credentials and grant a new access token."""
    if config.FEATURES_SIGN_UP_DISABLED:
        raise exceptions.SignUpDisabled()

    try:
        account = await actions.create_account(
            db_client,
            payload.username,
            payload.password,
            email=payload.email,
            storage_quota=config.STORAGE_QUOTA,
        )
    except errors.UserAlreadyExists as exc:
        raise exceptions.UserAlreadyExists(str(exc)) from exc

    return Tokens(
        access_token=security.create_access_token(str(account.user.id))
    )


@router.post("/refresh_token", response_model=Tokens)
async def refresh_token(curr_user_id: str = Depends(deps.current_user_id)):
    """Grant new access token based on current access token."""
    return Tokens(
        access_token=security.create_access_token(curr_user_id)
    )
