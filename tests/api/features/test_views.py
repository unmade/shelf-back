from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.config import config

if TYPE_CHECKING:
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]


async def test_list_features(client: TestClient):
    response = await client.get("/features/list")
    assert response.json() == {
        "items": [
            {
                "name": "max_file_size_to_thumbnail",
                "value": config.features.max_file_size_to_thumbnail,
            },
            {
                "name": "photos_library_path",
                "value": config.features.photos_library_path,
            },
            {
                "name": "sign_up_enabled",
                "value": config.features.sign_up_enabled,
            },
            {
                "name": "shared_links_enabled",
                "value": config.features.shared_links_enabled,
            },
            {
                "name": "upload_file_max_size",
                "value": config.features.upload_file_max_size,
            },
            {
                "name": "verification_required",
                "value": config.features.verification_required,
            },
        ],
    }
    assert response.status_code == 200
