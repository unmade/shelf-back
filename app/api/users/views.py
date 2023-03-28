from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.app.files.domain import File, Namespace
from app.app.users.domain import User
from app.infrastructure.provider import UseCases

from . import exceptions
from .schemas import IDRequest, ListBookmarksResponse

router = APIRouter()


@router.post("/bookmarks/add")
async def add_bookmark(
    payload: IDRequest,
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
) -> None:
    """Adds a file to user bookmarks."""
    try:
        await usecases.user.add_bookmark(namespace.owner_id, str(payload.id))
    except File.NotFound as exc:
        raise exceptions.FileNotFound() from exc


@router.get("/bookmarks/list")
async def list_bookmarks(
    user: User = Depends(deps.current_user),
    usecases: UseCases = Depends(deps.usecases),
) -> ListBookmarksResponse:
    """Lists user bookmarks."""
    bookmarks = await usecases.user.list_bookmarks(user.id)
    return ListBookmarksResponse(items=[bookmark.file_id for bookmark in bookmarks])


@router.post("/bookmarks/remove")
async def remove_bookmark(
    payload: IDRequest,
    user: User = Depends(deps.current_user),
    usecases: UseCases = Depends(deps.usecases),
) -> None:
    """Removes a file from user bookmarks."""
    await usecases.user.remove_bookmark(user.id, str(payload.id))
