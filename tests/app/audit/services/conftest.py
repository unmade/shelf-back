from __future__ import annotations

from unittest import mock

import pytest

from app.app.audit.repositories import IAuditTrailRepository
from app.app.audit.services import AuditTrailService


@pytest.fixture
def audit_trail_service():
    database = mock.MagicMock(audit_trail=mock.AsyncMock(IAuditTrailRepository))
    return AuditTrailService(database=database)
