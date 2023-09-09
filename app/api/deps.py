from __future__ import annotations

from typing import Annotated, AsyncIterator, TypeAlias

from fastapi import Depends, Query, Request
from fastapi.security import OAuth2PasswordBearer

from app.api.files.exceptions import DownloadNotFound
from app.app.audit.domain import CurrentUserContext
from app.app.audit.domain.current_user_context import CurrentUser
from app.app.auth.domain import AccessToken, TokenError
from app.app.files.domain import AnyFile, Namespace
from app.app.infrastructure.worker import IWorker
from app.app.users.domain import User
from app.infrastructure.context import UseCases

from . import exceptions, shortcuts

__all__ = [
    "CurrentUserDeps",
    "CurrentUserContextDeps",
    "NamespaceDeps",
    "UseCasesDeps",
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


async def current_user_ctx(
    usecases: UseCasesDeps,
    payload: AccessToken = Depends(token_payload),
) -> AsyncIterator[CurrentUserContext]:
    """Sets context about current user."""
    try:
        user = await usecases.user.user_service.get_by_id(payload.sub)
    except User.NotFound as exc:
        raise exceptions.UserNotFound() from exc

    current_user = CurrentUser(id=user.id, username=user.username)
    with CurrentUserContext(user=current_user) as ctx:
        yield ctx


async def current_user(ctx: CurrentUserContextDeps) -> CurrentUser:
    """Returns current user."""
    return ctx.user


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


CurrentUserDeps: TypeAlias = Annotated[CurrentUser, Depends(current_user)]
CurrentUserContextDeps: TypeAlias = Annotated[
    CurrentUserContext, Depends(current_user_ctx)
]
DownloadCacheDeps: TypeAlias = Annotated[AnyFile, Depends(download_cache)]
NamespaceDeps: TypeAlias = Annotated[Namespace, Depends(namespace)]
UseCasesDeps: TypeAlias = Annotated[UseCases, Depends(usecases)]
WorkerDeps: TypeAlias = Annotated[IWorker, Depends(worker)]
