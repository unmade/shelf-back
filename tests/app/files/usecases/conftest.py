from __future__ import annotations

from contextlib import AsyncExitStack
from unittest import mock

import pytest

from app.app.audit.services import AuditTrailService
from app.app.files.services import (
    ContentService,
    DuplicateFinderService,
    FileMemberService,
    FileService,
    MetadataService,
    NamespaceService,
    SharingService,
    ThumbnailService,
)
from app.app.files.services.file import FileCoreService
from app.app.files.usecases import NamespaceUseCase, SharingUseCase
from app.app.users.services import UserService


async def _atomic():
    yield AsyncExitStack()


@pytest.fixture
def ns_use_case():
    """A mocked NamespaceUseCase instance."""
    services = mock.MagicMock(
        content=mock.MagicMock(spec=ContentService),
        audit_trail=mock.MagicMock(spec=AuditTrailService),
        dupefinder=mock.MagicMock(spec=DuplicateFinderService),
        file=mock.MagicMock(spec=FileService, filecore=mock.MagicMock(FileCoreService)),
        metadata=mock.MagicMock(spec=MetadataService),
        namespace=mock.MagicMock(spec=NamespaceService),
        thumbnailer=mock.MagicMock(spec=ThumbnailService),
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
        file_member=mock.MagicMock(spec=FileMemberService),
        namespace=mock.MagicMock(spec=NamespaceService),
        sharing=mock.MagicMock(spec=SharingService),
        thumbnailer=mock.MagicMock(spec=ThumbnailService),
        user=mock.MagicMock(spec=UserService),
        atomic=_atomic,
    )
    return SharingUseCase(services=services)
