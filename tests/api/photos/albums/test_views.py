from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.app.users.domain import User
    from tests.api.conftest import TestClient


class TestList:
    url = "/photos/albums/list"

    async def test(self, client: TestClient, user: User):
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        assert response.status_code == 200
        assert len(response.json()["items"]) == 0
