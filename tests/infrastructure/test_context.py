from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.infrastructure.context import Infrastructure, Services
from app.infrastructure.database.edgedb import GelDatabase
from app.infrastructure.storage import FileSystemStorage, S3Storage

if TYPE_CHECKING:
    from pytest import FixtureRequest


class TestInfrastructure:
    @pytest.mark.anyio
    async def test_as_context_manager(
        self, gel_config, fs_storage_config, arq_worker_config, smtp_mail_config
    ):
        config = mock.MagicMock(
            database=gel_config,
            mail=smtp_mail_config,
            storage=fs_storage_config,
            worker=arq_worker_config,
        )
        async with Infrastructure(config) as infra:
            assert isinstance(infra, Infrastructure)

    @pytest.mark.parametrize(["config_name", "database_cls"], [
        ("gel_config", GelDatabase),
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


class TestServices:
    def test_atomic(self):
        # GIVEN
        infra = mock.MagicMock(Infrastructure)
        services = Services(infra)
        # WHEN
        services.atomic(attempts=5)
        # THEN
        infra.database.atomic.assert_called_once_with(attempts=5)
