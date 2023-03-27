from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.app.files.domain import Namespace
from app.app.users.domain import User
from app.infrastructure.provider import Services, UseCases

from . import exceptions
from .schemas import IDRequest, ListBookmarksResponse

router = APIRouter()


@router.post("/bookmarks/add")
async def add_bookmark(
    payload: IDRequest,
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
    services: Services = Depends(deps.services),
) -> None:
    """Add a file to user bookmarks."""
    if not await usecases.namespace.has_item_with_id(namespace.path, str(payload.id)):
        raise exceptions.FileNotFound()
    await services.user.add_bookmark(namespace.owner_id, payload.id)


@router.get("/bookmarks/list")
async def list_bookmarks(
    user: User = Depends(deps.current_user),
    services: Services = Depends(deps.services),
) -> ListBookmarksResponse:
    """List user bookmarks."""
    bookmarks = await services.user.list_bookmarks(user.id)
    return ListBookmarksResponse(items=bookmarks)


@router.post("/bookmarks/remove")
async def remove_bookmark(
    payload: IDRequest,
    user: User = Depends(deps.current_user),
    services: Services = Depends(deps.services),
) -> None:
    """Remove a file from user bookmarks."""
    await services.user.remove_bookmark(user.id, payload.id)
