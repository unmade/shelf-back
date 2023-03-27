from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.security import OAuth2PasswordRequestForm

from app import config
from app.api import deps
from app.api.exceptions import InvalidToken
from app.app.auth.domain import TokenError
from app.app.auth.usecases.auth import InvalidCredentials
from app.app.users.domain import User
from app.infrastructure.provider import UseCases

from . import exceptions
from .schemas import SignUpRequest, TokensSchema

router = APIRouter()


@router.post("/sign_in")
async def sign_in(
    form_data: OAuth2PasswordRequestForm = Depends(),
    usecases: UseCases = Depends(deps.usecases),
) -> TokensSchema:
    """Grant new access token for a given credentials."""

    username, password = form_data.username, form_data.password
    try:
        access, refresh = await usecases.auth.signin(username, password)
    except InvalidCredentials as exc:
        raise exceptions.InvalidCredentials() from exc

    return TokensSchema(access_token=access, refresh_token=refresh)


@router.post("/sign_up")
async def sign_up(
    payload: SignUpRequest,
    usecases: UseCases = Depends(deps.usecases),
) -> TokensSchema:
    """Create a new account with given credentials and grant a new access token."""
    if config.FEATURES_SIGN_UP_DISABLED:
        raise exceptions.SignUpDisabled()

    try:
       access, refresh = await usecases.auth.signup(
            payload.username,
            payload.password,
            storage_quota=config.STORAGE_QUOTA,
        )
    except User.AlreadyExists as exc:
        raise exceptions.UserAlreadyExists(str(exc)) from exc

    return TokensSchema(access_token=access, refresh_token=refresh)


@router.post("/refresh_token")
async def refresh_tokens(
    x_shelf_refresh_token: str | None = Header(default=None),
    usecases: UseCases = Depends(deps.usecases),
) -> TokensSchema:
    """Grant new access token based on current access token."""
    refresh_token = x_shelf_refresh_token
    if refresh_token is None:
        raise InvalidToken() from None

    try:
        access, refresh = await usecases.auth.rotate_tokens(refresh_token)
    except TokenError as exc:
        raise InvalidToken() from exc

    return TokensSchema(access_token=access, refresh_token=refresh)
