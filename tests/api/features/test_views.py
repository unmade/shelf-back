from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import config

if TYPE_CHECKING:
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


async def test_list_features(client: TestClient):
    response = await client.get("/features/list")
    assert response.json() == {
        "items": [
            {
                "name": "sign_up_disabled",
                "value": config.FEATURES_SIGN_UP_DISABLED,
            },
            {
                "name": "upload_file_max_size",
                "value": config.FEATURES_UPLOAD_FILE_MAX_SIZE,
            },
        ],
    }
    assert response.status_code == 200
