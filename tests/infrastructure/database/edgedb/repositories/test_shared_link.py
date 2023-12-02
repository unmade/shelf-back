from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest

from app.app.files.domain import File, SharedLink
from app.app.infrastructure.database import SENTINEL_ID
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from app.app.files.domain import Namespace
    from app.infrastructure.database.edgedb.repositories import SharedLinkRepository
    from tests.infrastructure.database.edgedb.conftest import (
        FileFactory,
        SharedLinkFactory,
    )

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
    return SharedLink(id=obj.id, file_id=obj.file.id, token=obj.token)


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
        file_id = uuid.uuid4()
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


class TestListByNS:
    async def test(
        self,
        shared_link_repo: SharedLinkRepository,
        file_factory: FileFactory,
        shared_link_factory: SharedLinkFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        files = [
            await file_factory(ns_path=namespace_a.path, path="f (1).txt"),
            await file_factory(ns_path=namespace_a.path, path="f (2).txt"),
            await file_factory(ns_path=namespace_b.path, path="x-1.txt"),
            await file_factory(ns_path=namespace_b.path, path="x-2.txt"),
        ]
        links = [await shared_link_factory(file.id) for file in files]
        # WHEN
        result = await shared_link_repo.list_by_ns(namespace_a.path)
        # THEN
        assert result == links[:2]
        # WHEN
        result = await shared_link_repo.list_by_ns(namespace_b.path)
        # THEN
        assert result == links[2:]


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
        file_id = uuid.uuid4()
        link = SharedLink(id=SENTINEL_ID, file_id=file_id, token="secret")
        with pytest.raises(File.NotFound):
            await shared_link_repo.save(link)
