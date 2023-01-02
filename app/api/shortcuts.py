from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi.responses import Response

from app import actions, errors, mediatypes
from app.cache import disk_cache
from app.entities import Namespace

from .files import exceptions

if TYPE_CHECKING:
    from app.typedefs import DBClient


@disk_cache(ttl="24h", key="{file_id}:{size}:{mtime}")
async def get_cached_thumbnail(
    db_client: DBClient,
    namespace: Namespace,
    file_id: UUID,
    size: int,
    mtime: float,
) -> Response:
    """
    Return a prepared response with a thumbnail of a given file ID.

    If thumbnail doesn't exist than it will be created and cached.
    """
    try:
        file, thumbnail = await actions.get_thumbnail(
            db_client, namespace, file_id, size=size,
        )
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=str(file_id)) from exc
    except errors.IsADirectory as exc:
        raise exceptions.IsADirectory(path=str(file_id)) from exc
    except errors.ThumbnailUnavailable as exc:
        raise exceptions.ThumbnailUnavailable(path=str(file_id)) from exc

    filename = file.name.encode("utf-8").decode("latin-1")

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(thumbnail)),
        "Content-Type": mediatypes.IMAGE_WEBP,
        "Cache-Control": "private, max-age=31536000, no-transform",
    }

    return Response(thumbnail, headers=headers)
