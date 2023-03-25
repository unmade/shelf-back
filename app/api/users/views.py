from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.domain.entities import Namespace
from app.infrastructure.provider import Manager, Service

from . import exceptions
from .schemas import IDRequest, ListBookmarksResponse

router = APIRouter()


@router.post("/bookmarks/add")
async def add_bookmark(
    payload: IDRequest,
    namespace: Namespace = Depends(deps.namespace),
    managers: Manager = Depends(deps.managers),
    services: Service = Depends(deps.services),
) -> None:
    """Add a file to user bookmarks."""
    if not await managers.namespace.has_item_with_id(namespace.path, str(payload.id)):
        raise exceptions.FileNotFound()
    await services.user.add_bookmark(namespace.owner_id, payload.id)


@router.get("/bookmarks/list")
async def list_bookmarks(
    user_id: str = Depends(deps.current_user_id),
    services: Service = Depends(deps.services),
) -> ListBookmarksResponse:
    """List user bookmarks."""
    bookmarks = await services.user.list_bookmarks(user_id)
    return ListBookmarksResponse(items=bookmarks)


@router.post("/bookmarks/remove")
async def remove_bookmark(
    payload: IDRequest,
    user_id: str = Depends(deps.current_user_id),
    services: Service = Depends(deps.services),
) -> None:
    """Remove a file from user bookmarks."""
    await services.user.remove_bookmark(user_id, payload.id)
