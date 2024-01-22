from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.app.files.services import ContentService
from app.app.files.usecases.namespace import NamespaceUseCase
from app.infrastructure.context import UseCases

if TYPE_CHECKING:
    from app.worker.main import ARQContext


@pytest.fixture
def arq_context() -> ARQContext:
    return {
        "usecases": mock.MagicMock(
            UseCases,
            namespace=mock.MagicMock(
                NamespaceUseCase,
                content=mock.MagicMock(ContentService),
            ),
        ),
        "_stack": AsyncExitStack(),
    }
