from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.domain.entities import Namespace

if TYPE_CHECKING:
    from app.app.services import NamespaceService
    from app.domain.entities import User

pytestmark = [pytest.mark.asyncio]


class TestCreate:
    async def test(self, user: User, namespace_service: NamespaceService):
        namespace = await namespace_service.create("admin", owner_id=user.id)
        assert namespace.id is not None
        assert namespace == Namespace.construct(
            id=mock.ANY,
            path="admin",
            owner_id=user.id,
        )
