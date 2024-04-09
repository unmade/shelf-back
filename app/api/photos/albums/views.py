from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDeps
from app.api.paginator import Page

from .schemas import AlbumSchema

router = APIRouter()


@router.get("/list")
async def list_albums(
    _: CurrentUserDeps,
    page: Annotated[int, Query(ge=1)] = 1,
) -> Page[AlbumSchema]:
    """Lists media items current user has."""
    return Page(
        page=page,
        items=[],
    )
