from __future__ import annotations

import operator
import os.path
from typing import TYPE_CHECKING

import pytest

from app.app.photos.domain import MediaItem
from app.config import config
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:

    from app.app.files.domain import File, Namespace
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb.repositories import MediaItemRepository
    from tests.infrastructure.database.edgedb.conftest import (
        FileFactory,
        MediaItemFactory,
    )

pytestmark = [pytest.mark.anyio, pytest.mark.database]


def _from_file(file: File) -> MediaItem:
    return MediaItem(
        file_id=file.id,
        name=file.name,
        size=file.size,
        mtime=file.mtime,
        mediatype=file.mediatype,  # type: ignore
    )


class TestListByUserID:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        file_factory: FileFactory,
        namespace: Namespace,
        user: User,
    ):
        # GIVEN
        await file_factory(
            namespace.path,
            os.path.join(config.features.photos_library_path, "f.txt"),
        )
        items = [
            await media_item_factory(user.id, "im.jpg", mediatype=MediaType.IMAGE_JPEG),
            await media_item_factory(user.id, "im.png", mediatype=MediaType.IMAGE_PNG),
        ]
        # WHEN
        result = await media_item_repo.list_by_user_id(user.id, offset=0)
        # THEN
        assert result == sorted(items, key=operator.attrgetter("mtime"), reverse=True)
