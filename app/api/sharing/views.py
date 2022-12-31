from __future__ import annotations

import secrets

from edgedb import AsyncIOClient
from fastapi import APIRouter, Depends

from app import crud, errors
from app.api import deps
from app.api.files import exceptions as file_exceptions
from app.api.files import schemas as file_schemas
from app.cache import cache
from app.entities import Namespace

from . import schemas

router = APIRouter()


@router.post("/create_shared_link", response_model=schemas.CreateSharedLinkResponse)
async def create_shared_link(
    payload: file_schemas.PathRequest,
    db_client: AsyncIOClient = Depends(deps.db_client),
    namespace: Namespace = Depends(deps.namespace),
):
    """Create a shared link for a file in a given path."""
    try:
        file = await crud.file.get(db_client, namespace.path, payload.path)
    except errors.FileNotFound as exc:
        raise file_exceptions.PathNotFound(path=payload.path) from exc

    key = secrets.token_urlsafe(16)
    await cache.set(key, value=f"{namespace.path}:{file.id}")
    return schemas.CreateSharedLinkResponse.construct(key=key)
