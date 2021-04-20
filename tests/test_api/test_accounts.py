from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from app.entities import User
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


async def test_get_current(client: TestClient, user: User):
    response = await client.login(user.id).get("/accounts/get_current")
    data = response.json()
    assert data["username"] == user.username
    assert data["email"] is None
    assert data["first_name"] == ""
    assert data["last_name"] == ""
    assert response.status_code == 200
