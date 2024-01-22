from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.api.photos.exceptions import MediaItemNotFound
from app.app.photos.domain import MediaItem

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]


class TestAddAutoCategoryBatch:
    url = "/-/photos/add_category_batch"

    async def test(self, client: TestClient, photos_use_case: MagicMock):
        # GIVEN
        file_id = uuid.uuid4()
        categories = [
            (MediaItem.Category.Name.ANIMALS, 92),
            (MediaItem.Category.Name.PETS, 94),
        ]
        payload = {
            "file_id": str(file_id),
            "categories": [
                {
                    "name": name,
                    "probability": probability,
                }
                for name, probability in categories
            ]
        }
        # WHEN
        client.mock_service_token()
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.auto_add_category_batch.assert_awaited_once_with(
            file_id, categories=categories
        )
        assert response.status_code == 200

    async def test_when_media_item_not_found(
        self,
        client: TestClient,
        photos_use_case: MagicMock,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        categories = [
            (MediaItem.Category.Name.ANIMALS, 92),
            (MediaItem.Category.Name.PETS, 94),
        ]
        payload = {
            "file_id": str(file_id),
            "categories": [
                {
                    "name": name,
                    "probability": probability,
                }
                for name, probability in categories
            ]
        }
        photos_use_case.auto_add_category_batch.side_effect = MediaItem.NotFound
        # WHEN
        client.mock_service_token()
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.auto_add_category_batch.assert_awaited_once_with(
            file_id, categories=categories
        )
        assert response.status_code == 404
        assert response.json() == MediaItemNotFound().as_dict()
