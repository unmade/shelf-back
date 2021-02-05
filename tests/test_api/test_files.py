from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ..conftest import TestClient


@pytest.mark.parametrize(["path", "name", "expected_path", "hidden"], [
    ("Folder", "Folder", None, False),
    ("Nested/Path/Folder", "Folder", None, False),
    (".Hidden Folder", ".Hidden Folder", None, True),
    (" Whitespaces ", "Whitespaces", "Whitespaces", False),
])
def test_create_folder(
    client: TestClient, user_factory, path, name, expected_path, hidden,
):
    user = user_factory()
    payload = {"path": path}
    response = client.login(user.id).post("/files/create_folder", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.pop("id")
    assert data.pop("mtime")
    assert data == {
        "type": "folder",
        "name": name,
        "path": expected_path or path,
        "size": 0,
        "hidden": hidden,
    }


def test_create_folder_but_folder_already_exists(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "Trash"}
    response = client.login(user.id).post("/files/create_folder", json=payload)
    assert response.status_code == 400
    assert response.json() == {
        "code": "ALREADY_EXISTS",
        "message": "Already exists.",
    }


def test_list_folder_unauthorized(client: TestClient):
    response = client.post("/files/list_folder")
    assert response.status_code == 401
