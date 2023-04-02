from __future__ import annotations

from unittest import mock

import pytest
from fastapi import FastAPI

from app.api.main import Lifespan
from app.infrastructure.provider import Provider


class TestLifeSpan:
    def test_init(self):
        with (
            mock.patch.object(Lifespan, "_create_database") as create_database_mock,
            mock.patch.object(Lifespan, "_create_storage") as create_storage_mock,
        ):
            lifespan = Lifespan()
        assert lifespan.database == create_database_mock.return_value
        assert lifespan.storage == create_storage_mock.return_value
        create_database_mock.assert_called_once_with()
        create_storage_mock.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_as_context_manager(self):
        app = mock.MagicMock(FastAPI)
        with (
            mock.patch.object(Lifespan, "_create_database"),
            mock.patch.object(Lifespan, "_create_storage"),
        ):
            lifespan = Lifespan()
            async with lifespan(app=app) as state:
                assert state == {"provider": mock.ANY}
                assert isinstance(state["provider"], Provider)
