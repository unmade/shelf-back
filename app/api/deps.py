from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query, Request
from fastapi.security import OAuth2PasswordBearer

from app.api.files.exceptions import DownloadNotFound
from app.app.audit.domain import CurrentUserContext
from app.app.audit.domain.current_user_context import CurrentUser
from app.app.auth.domain import AccessToken, TokenError
from app.app.files.domain import AnyFile, Namespace
from app.app.infrastructure.worker import IWorker
from app.app.users.domain import User
from app.config import config
from app.infrastructure.context import UseCases

from . import exceptions, shortcuts

__all__ = [
    "CurrentUserDeps",
    "CurrentUserContextDeps",
    "NamespaceDeps",
    "ServiceTokenDeps",
    "UseCasesDeps",
    "VerifiedCurrentUserDeps",
    "WorkerDeps",
]

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/sign_in", auto_error=False)


async def usecases(request: Request):
    return request.state.usecases


async def worker(request: Request):
    return request.state.worker


def token_payload(token: str | None = Depends(reusable_oauth2)) -> AccessToken:
    """Returns payload from authentication token."""
    if token is None:
        raise exceptions.MissingToken() from None

    try:
        return AccessToken.decode(token)
    except TokenError as exc:
        raise exceptions.InvalidToken() from exc


async def _user(
    usecases: UseCasesDeps,
    payload: AccessToken = Depends(token_payload),
) -> User:
    """Returns currently authenticated user."""
    try:
        return await usecases.user.user_service.get_by_id(UUID(payload.sub))
    except User.NotFound as exc:
        raise exceptions.UserNotFound() from exc


async def current_user_ctx(
    user: User = Depends(_user)
) -> AsyncIterator[CurrentUserContext]:
    """Sets context about current user."""
    current_user = CurrentUser(id=user.id, username=user.username)
    with CurrentUserContext(user=current_user) as ctx:
        yield ctx


async def current_user(
    _: CurrentUserContextDeps, user: User = Depends(_user)
) -> User:
    """Returns current user."""
    return user


async def verified_current_user(user: CurrentUserDeps) -> User:
    """Returns current user if it is a verified user."""
    if config.features.verification_required and not user.is_verified():
        raise exceptions.UnverifiedUser() from None
    return user


async def download_cache(key: str = Query(None)):
    value = await shortcuts.pop_download_cache(key)
    if not value:
        raise DownloadNotFound()
    return value


async def namespace(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> Namespace:
    """Returns a namespace for a user from a token payload."""
    # If namespace is not found, we should fail, so don't catch Namespace.NotFound here.
    # We should fail because the system is in the inconsistent state - user exists,
    # but doesn't have a namespace
    return await usecases.namespace.namespace.get_by_owner_id(user.id)


async def service_token(token: str | None = Depends(reusable_oauth2)):
    """Requires a service token."""
    if not token:
        raise exceptions.MissingToken() from None

    if token != config.auth.service_token:
        raise exceptions.InvalidToken() from None


CurrentUserDeps = Annotated[User, Depends(current_user)]
CurrentUserContextDeps = Annotated[
    CurrentUserContext, Depends(current_user_ctx)
]
DownloadCacheDeps = Annotated[AnyFile, Depends(download_cache)]
NamespaceDeps = Annotated[Namespace, Depends(namespace)]
ServiceTokenDeps = Annotated[None, Depends(service_token)]
UseCasesDeps = Annotated[UseCases, Depends(usecases)]
VerifiedCurrentUserDeps = Annotated[User, Depends(verified_current_user)]
WorkerDeps = Annotated[IWorker, Depends(worker)]
