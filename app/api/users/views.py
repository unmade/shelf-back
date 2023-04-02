from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDeps, NamespaceDeps, UseCasesDeps
from app.app.files.domain import File

from . import exceptions
from .schemas import IDRequest, ListBookmarksResponse

router = APIRouter()


@router.post("/bookmarks/add")
async def add_bookmark(
    payload: IDRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> None:
    """Adds a file to user bookmarks."""
    try:
        await usecases.user.add_bookmark(namespace.owner_id, str(payload.id))
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
    await usecases.user.remove_bookmark(user.id, str(payload.id))
