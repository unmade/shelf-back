from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def test_list_folder_unauthorized(client: TestClient):
    response = client.post("/files/list_folder")
    assert response.status_code == 401
