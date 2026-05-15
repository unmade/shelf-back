from __future__ import annotations

from unittest import mock

import pytest

from app.app.audit.services import AuditTrailService
from app.app.blobs.services import (
    BlobContentProcessor,
    BlobMetadataService,
    BlobThumbnailService,
)
from app.app.files.services import (
    FileService,
    NamespaceService,
    SharingService,
)
from app.app.files.services.file import FileCoreService
from app.app.files.usecases import NamespaceUseCase, SharingUseCase
from app.app.users.services import UserService


@pytest.fixture
def ns_use_case():
    """A mocked NamespaceUseCase instance."""
    services = mock.MagicMock(
        audit_trail=mock.MagicMock(spec=AuditTrailService),
        blob_metadata=mock.MagicMock(spec=BlobMetadataService),
        blob_processor=mock.MagicMock(spec=BlobContentProcessor),
        file=mock.MagicMock(spec=FileService, filecore=mock.MagicMock(FileCoreService)),
        namespace=mock.MagicMock(spec=NamespaceService),
        thumbnailer=mock.MagicMock(spec=BlobThumbnailService),
        user=mock.MagicMock(spec=UserService),
    )
    return NamespaceUseCase(services=services)


@pytest.fixture
def sharing_use_case():
    """A mocked SharingManager instance."""
    services = mock.MagicMock(
        file=mock.MagicMock(
            FileService,
            filecore=mock.MagicMock(FileCoreService),
        ),
        sharing=mock.MagicMock(spec=SharingService),
        thumbnailer=mock.MagicMock(spec=BlobThumbnailService),
        user=mock.MagicMock(spec=UserService),
    )
    return SharingUseCase(services=services)
