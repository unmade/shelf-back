from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest

from app.app.files.domain import SENTINEL_ID, File, SharedLink
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.repositories import SharedLinkRepository

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def _exists_by_token(token: str) -> bool:
    query = """
        SELECT EXISTS (
            SELECT SharedLink { id, token, file: { id } }
            FILTER .token = <str>$token
        )
    """
    return cast(
        bool,
        await db_context.get().query_required_single(query, token=token)
    )


async def _get_by_token(token: str) -> SharedLink:
    query = """
        SELECT SharedLink { id, token, file: { id } }
        FILTER .token = <str>$token
    """
    obj = await db_context.get().query_required_single(query, token=token)
    return SharedLink(id=obj.id, file_id=str(obj.file.id), token=obj.token)


class TestDelete:
    async def test(
        self, shared_link_repo: SharedLinkRepository, shared_link: SharedLink
    ):
        await shared_link_repo.delete(shared_link.token)
        assert not await _exists_by_token(shared_link.token)


class TestGetByFileID:
    async def test(
        self, shared_link_repo: SharedLinkRepository, shared_link: SharedLink,
    ):
        link = await shared_link_repo.get_by_file_id(shared_link.file_id)
        assert link == shared_link

    async def test_when_link_does_not_exist(
        self, shared_link_repo: SharedLinkRepository
    ):
        file_id = str(uuid.uuid4())
        with pytest.raises(SharedLink.NotFound):
            await shared_link_repo.get_by_file_id(file_id)


class TestGetByToken:
    async def test(
        self, shared_link_repo: SharedLinkRepository, shared_link: SharedLink
    ):
        link = await shared_link_repo.get_by_token(shared_link.token)
        assert link == shared_link

    async def test_when_link_does_not_exist(
        self, shared_link_repo: SharedLinkRepository
    ):
        token = "shared-link-token"
        with pytest.raises(SharedLink.NotFound):
            await shared_link_repo.get_by_token(token)


class TestSave:
    async def test(self, shared_link_repo: SharedLinkRepository, file: File):
        link = SharedLink(id=SENTINEL_ID, file_id=file.id, token="secret")
        result = await shared_link_repo.save(link)
        assert result.id != SENTINEL_ID
        assert result == await _get_by_token(link.token)

    async def test_idempotency(
        self, shared_link_repo: SharedLinkRepository, shared_link: SharedLink
    ):
        result = await shared_link_repo.save(shared_link)
        assert result.id != SENTINEL_ID
        assert result == shared_link

    async def test_when_file_does_not_exist(
        self, shared_link_repo: SharedLinkRepository,
    ):
        file_id = str(uuid.uuid4())
        link = SharedLink(id=SENTINEL_ID, file_id=file_id, token="secret")
        with pytest.raises(File.NotFound):
            await shared_link_repo.save(link)
