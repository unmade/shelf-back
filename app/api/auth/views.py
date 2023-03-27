from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.security import OAuth2PasswordRequestForm

from app import config, tokens
from app.api import deps
from app.api.exceptions import InvalidToken
from app.app.users.domain import User
from app.infrastructure.provider import Services, UseCases

from . import exceptions
from .schemas import SignUpRequest, TokensSchema

router = APIRouter()


@router.post("/sign_in")
async def sign_in(
    form_data: OAuth2PasswordRequestForm = Depends(),
    services: Services = Depends(deps.services),
) -> TokensSchema:
    """Grant new access token for a given credentials."""

    username, password = form_data.username, form_data.password
    user = await services.user.verify_credentials(username, password)
    if user is None:
        raise exceptions.InvalidCredentials()

    access_token, refresh_token = await tokens.create_tokens(str(user.id))
    return TokensSchema(access_token=access_token, refresh_token=refresh_token)


@router.post("/sign_up")
async def sign_up(
    payload: SignUpRequest,
    services: Services = Depends(deps.services),
    usecases: UseCases = Depends(deps.usecases),
) -> TokensSchema:
    """Create a new account with given credentials and grant a new access token."""
    if config.FEATURES_SIGN_UP_DISABLED:
        raise exceptions.SignUpDisabled()

    try:
       user = await services.user.create(
            payload.username,
            payload.password,
            storage_quota=config.STORAGE_QUOTA,
        )
    except User.AlreadyExists as exc:
        raise exceptions.UserAlreadyExists(str(exc)) from exc

    await usecases.namespace.create_namespace(user.username, owner_id=user.id)

    access_token, refresh_token = await tokens.create_tokens(str(user.id))
    return TokensSchema(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh_token")
async def refresh_token(
    x_shelf_refresh_token: str | None = Header(default=None)
) -> TokensSchema:
    """Grant new access token based on current access token."""
    refresh_token = x_shelf_refresh_token
    if refresh_token is None:
        raise InvalidToken() from None

    try:
        access_token, refresh_token = await tokens.rotate_tokens(refresh_token)
    except tokens.TokenError as exc:
        raise InvalidToken() from exc

    return TokensSchema(access_token=access_token, refresh_token=refresh_token)
