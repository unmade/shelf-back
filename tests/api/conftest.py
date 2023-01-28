from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

if TYPE_CHECKING:
    from fastapi import FastAPI


@pytest.fixture
def ns_service(app: FastAPI):
    """A mock of a NamespaceService instance."""
    service = app.state.provider.service
    ns_service_mock = mock.MagicMock(service.namespace)
    with mock.patch.object(service, "namespace", ns_service_mock) as mocked:
        yield mocked


@pytest.fixture
def user_service(app: FastAPI):
    """A mock of a UserService instance."""
    service = app.state.provider.service
    service_mock = mock.MagicMock(service.user)
    with mock.patch.object(service, "user", service_mock) as mocked:
        yield mocked
