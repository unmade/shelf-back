from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture
def ns_manager(app: FastAPI):
    """A mocked instance of a NamespaceManager."""
    managers = app.state.provider.manager
    new = mock.MagicMock(managers.namespace)
    with mock.patch.object(managers, "namespace", new) as patch:
        yield patch


@pytest.fixture
def ns_service(app: FastAPI):
    """A mock of a NamespaceService instance."""
    service = app.state.provider.service
    new = mock.MagicMock(service.namespace)
    with mock.patch.object(service, "namespace", new) as patch:
        yield patch


@pytest.fixture
def user_service(app: FastAPI):
    """A mock of a UserService instance."""
    service = app.state.provider.service
    spec = mock.MagicMock(service.user)
    with mock.patch.object(service, "user", spec) as mocked:
        yield mocked


@pytest.fixture
def sharing_manager(app: FastAPI):
    """A mocked instance of a SharingManager."""
    managers = app.state.provider.manager
    new = mock.MagicMock(managers.sharing)
    with mock.patch.object(managers, "sharing", new) as patch:
        yield patch
