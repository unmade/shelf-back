from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import Namespace
from app.app.infrastructure.database import SENTINEL_ID

if TYPE_CHECKING:
    from app.app.files.services import NamespaceService

pytestmark = [pytest.mark.anyio, pytest.mark.database]


@pytest.fixture
def ns_service():
    from app.app.files.repositories import INamespaceRepository
    from app.app.files.services import NamespaceService
    from app.app.files.services.file import FileCoreService

    database = mock.MagicMock(namespace=mock.MagicMock(INamespaceRepository))
    filecore = mock.MagicMock(FileCoreService)
    return NamespaceService(database=database, filecore=filecore)


class TestCreate:
    async def test(self, ns_service: NamespaceService):
        # GIVEN
        ns_path, owner_id = "admin", uuid.uuid4()
        db = cast(mock.MagicMock, ns_service.db)
        filecore = cast(mock.MagicMock, ns_service.filecore)
        # WHEN
        namespace = await ns_service.create(ns_path, owner_id=owner_id)
        # THEN
        assert namespace == db.namespace.save.return_value
        db.namespace.save.assert_awaited_once_with(
            Namespace.model_construct(
                id=SENTINEL_ID,
                path=ns_path,
                owner_id=owner_id,
            )
        )
        filecore.create_folder.assert_has_awaits([
            mock.call(namespace.path, "."),
            mock.call(namespace.path, "Trash"),
        ])


class TestGetByOwnerID:
    async def test(self, ns_service: NamespaceService):
        # GIVEN
        owner_id = uuid.uuid4()
        db = cast(mock.MagicMock, ns_service.db)
        # WHEN
        result = await ns_service.get_by_owner_id(owner_id)
        # THEN
        assert result == db.namespace.get_by_owner_id.return_value
        db.namespace.get_by_owner_id.assert_awaited_once_with(owner_id)


class TestGetByPath:
    async def test(self, ns_service: NamespaceService):
        # GIVEN
        ns_path = "admin"
        db = cast(mock.MagicMock, ns_service.db)
        # WHEN
        result = await ns_service.get_by_path(ns_path)
        # THEN
        assert result == db.namespace.get_by_path.return_value
        db.namespace.get_by_path.assert_awaited_once_with(ns_path)


class TestGetSpaceUsedByOwnerID:
    async def test(self, ns_service: NamespaceService):
        # GIVEN
        owner_id = uuid.uuid4()
        db = cast(mock.MagicMock, ns_service.db)
        # WHEN
        result = await ns_service.get_space_used_by_owner_id(owner_id)
        # THEN
        assert result == db.namespace.get_space_used_by_owner_id.return_value
        db.namespace.get_space_used_by_owner_id.assert_awaited_once_with(owner_id)
