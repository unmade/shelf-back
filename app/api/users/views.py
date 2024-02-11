from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDeps, NamespaceDeps, UseCasesDeps
from app.app.files.domain import File
from app.app.users.domain import User

from . import exceptions
from .schemas import (
    IDRequest,
    ListBookmarksResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)

router = APIRouter()


@router.post("/bookmarks/add")
async def add_bookmark(
    payload: IDRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> None:
    """Adds a file to user bookmarks."""
    try:
        await usecases.user.add_bookmark(
            user_id=namespace.owner_id,
            file_id=payload.id,
            ns_path=namespace.path,
        )
    except File.NotFound as exc:
        raise exceptions.FileNotFound() from exc


@router.get("/bookmarks/list")
async def list_bookmarks(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> ListBookmarksResponse:
    """Lists user bookmarks."""
    bookmarks = await usecases.user.list_bookmarks(user.id)
    return ListBookmarksResponse(items=[bookmark.file_id for bookmark in bookmarks])


@router.post("/bookmarks/remove")
async def remove_bookmark(
    payload: IDRequest,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> None:
    """Removes a file from user bookmarks."""
    await usecases.user.remove_bookmark(user.id, payload.id)


@router.post("/send_email_verification_code")
async def send_email_verification_code(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> None:
    """Sends a verification code to the user email."""
    try:
        await usecases.user.send_email_verification_code(user.id)
    except User.EmailAlreadyVerified as exc:
        raise exceptions.UserEmailAlreadyVerified() from exc
    except User.EmailIsMissing as exc:
        raise exceptions.UserEmailIsMissing() from exc


@router.post("/verify_email")
async def verify_email(
    payload: VerifyEmailRequest,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> VerifyEmailResponse:
    """Verifies current user email."""
    verified = await usecases.user.verify_email(user.id, payload.code)
    return VerifyEmailResponse(verified=verified)
