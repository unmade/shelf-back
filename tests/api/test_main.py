from __future__ import annotations

from unittest import mock

import pytest
from fastapi import FastAPI

from app.api.main import Lifespan
from app.infrastructure.context import UseCases


class TestLifeSpan:
    @pytest.mark.anyio
    async def test_as_context_manager(self):
        app = mock.MagicMock(FastAPI)
        with mock.patch("app.infrastructure.context.Infrastructure"):
            lifespan = Lifespan()
            async with lifespan(app=app) as state:
                assert state == {"usecases": mock.ANY, "worker": mock.ANY}
                assert isinstance(state["usecases"], UseCases)
