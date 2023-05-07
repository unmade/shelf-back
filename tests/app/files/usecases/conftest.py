from __future__ import annotations

from unittest import mock

import pytest

from app.app.audit.services import AuditTrailService
from app.app.files.services import (
    DuplicateFinderService,
    FileCoreService,
    FileService,
    MetadataService,
    NamespaceService,
    SharingService,
)
from app.app.files.usecases import NamespaceUseCase, SharingUseCase
from app.app.users.services import UserService


@pytest.fixture
def ns_use_case():
    """A mocked NamespaceUseCase instance."""
    return NamespaceUseCase(
        audit_trail=mock.MagicMock(spec=AuditTrailService),
        dupefinder=mock.MagicMock(spec=DuplicateFinderService),
        file=mock.MagicMock(spec=FileService),
        filecore=mock.MagicMock(spec=FileCoreService),
        metadata=mock.MagicMock(spec=MetadataService),
        namespace=mock.MagicMock(spec=NamespaceService),
        user=mock.MagicMock(spec=UserService),
    )


@pytest.fixture
def sharing_use_case():
    """A mocked SharingManager instance."""
    return SharingUseCase(
        filecore=mock.MagicMock(spec=FileCoreService),
        sharing=mock.MagicMock(spec=SharingService),
    )
