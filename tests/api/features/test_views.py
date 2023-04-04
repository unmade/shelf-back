from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import config

if TYPE_CHECKING:
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


async def test_list_features(client: TestClient):
    response = await client.get("/features/list")
    assert response.json() == {
        "items": [
            {
                "name": "sign_up_disabled",
                "value": config.features.sign_up_disabled,
            },
            {
                "name": "upload_file_max_size",
                "value": config.features.upload_file_max_size,
            },
        ],
    }
    assert response.status_code == 200
