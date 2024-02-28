from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDeps, UseCasesDeps

from .schemas import (
    AddBookmarkBatchRequest,
    ListBookmarksResponse,
    RemoveBookmarkBatchRequest,
)

router = APIRouter()


@router.post("/bookmarks/add_batch")
async def add_bookmark_batch(
    payload: AddBookmarkBatchRequest,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> None:
    """Adds multiple files to user bookmarks."""
    await usecases.user.add_bookmark_batch(user.id, payload.file_ids)


@router.get("/bookmarks/list")
async def list_bookmarks(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> ListBookmarksResponse:
    """Lists user bookmarks."""
    bookmarks = await usecases.user.list_bookmarks(user.id)
    return ListBookmarksResponse(items=[bookmark.file_id for bookmark in bookmarks])


@router.post("/bookmarks/remove_batch")
async def remove_bookmark_batch(
    payload: RemoveBookmarkBatchRequest,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> None:
    """Removes multiple files from user bookmarks."""
    await usecases.user.remove_bookmark_batch(user.id, payload.file_ids)
