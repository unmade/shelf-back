from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.app.blobs.services import (
    BlobContentProcessor,
    BlobService,
    BlobThumbnailService,
)
from app.app.files.services import FileService
from app.app.files.services.file import FileCoreService
from app.app.files.usecases.namespace import NamespaceUseCase
from app.infrastructure.context import UseCases

if TYPE_CHECKING:
    from app.worker.main import ARQContext


@pytest.fixture
def arq_context() -> ARQContext:
    return {
        "usecases": mock.MagicMock(
            UseCases,
            blob=mock.MagicMock(BlobService),
            blob_content_processor=mock.MagicMock(BlobContentProcessor),
            namespace=mock.MagicMock(
                NamespaceUseCase,
                file=mock.MagicMock(
                    FileService,
                    filecore=mock.MagicMock(FileCoreService),
                ),
                thumbnailer=mock.MagicMock(BlobThumbnailService),
            ),
        ),
        "_stack": AsyncExitStack(),
    }
