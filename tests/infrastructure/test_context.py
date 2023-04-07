from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.infrastructure.context import Infrastructure
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.storage import FileSystemStorage, S3Storage

if TYPE_CHECKING:
    from pytest import FixtureRequest


class TestInfrastructure:
    @pytest.mark.asyncio
    async def test_as_context_manager(self, edgedb_config, fs_storage_config):
        async with Infrastructure(edgedb_config, fs_storage_config) as infra:
            assert isinstance(infra, Infrastructure)

    @pytest.mark.parametrize(["config_name", "database_cls"], [
        ("edgedb_config", EdgeDBDatabase),
    ])
    def test_get_database(self, request: FixtureRequest, config_name, database_cls):
        config = request.getfixturevalue(config_name)
        database = Infrastructure._get_database(config)
        assert isinstance(database, database_cls)

    @pytest.mark.parametrize(["config_name", "storage_cls"], [
        ("fs_storage_config", FileSystemStorage),
        ("s3_storage_config", S3Storage),
    ])
    def test_get_storage(self, request: FixtureRequest, config_name, storage_cls):
        config = request.getfixturevalue(config_name)
        storage = Infrastructure._get_storage(config)
        assert isinstance(storage, storage_cls)
