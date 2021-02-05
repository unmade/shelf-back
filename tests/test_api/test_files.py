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
    # TODO: test with path like './Folder', '../Folder', 'Folder/./Folder', etc...
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


def test_delete_immediately(client: TestClient, user_factory):
    user = user_factory()
    name = path = "Test Folder"
    payload = {"path": path}
    client.login(user.id)
    client.post("/files/create_folder", json=payload)
    response = client.post("/files/delete_immediately", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.pop("id")
    assert data.pop("mtime")
    assert data == {
        "type": "folder",
        "name": name,
        "path": path,
        "size": 0,
        "hidden": False,
    }


def test_delete_immediately_but_path_not_found(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "Test Folder"}
    response = client.login(user.id).post("/files/delete_immediately", json=payload)
    assert response.status_code == 404
    assert response.json() == {
        "code": "PATH_NOT_FOUND",
        "message": "Path not found."
    }


@pytest.mark.parametrize("path", [".", "Trash"])
def test_delete_immediately_but_it_is_a_special_folder(
    client: TestClient, user_factory, path,
):
    user = user_factory()
    payload = {"path": path}
    response = client.login(user.id).post("/files/delete_immediately", json=payload)
    assert response.status_code == 400
    assert response.json() == {
        "code": "INVALID_OPERATION",
        "message": "Invalid operation.",
    }


def test_list_folder_unauthorized(client: TestClient):
    response = client.post("/files/list_folder")
    assert response.status_code == 401
