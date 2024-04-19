from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import Album
from app.infrastructure.database.edgedb.repositories import AlbumRepository
from app.toolkit import timezone

if TYPE_CHECKING:
    from app.app.users.domain import User

pytestmark = [pytest.mark.anyio, pytest.mark.database]


class TestSave:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        user: User,
    ):
        # GIVEN
        entity = Album(
            id=SENTINEL_ID,
            title="New Album",
            owner_id=user.id,
            created_at=timezone.now(),
        )
        # WHEN
        result = await album_repo.save(entity)
        # THEN
        assert result.id != SENTINEL_ID
        assert result.title == entity.title
        assert result.created_at == entity.created_at
        assert result.owner_id == entity.owner_id
        assert result.cover is None
