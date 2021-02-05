from __future__ import annotations

import secrets
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


def test_download_file(client: TestClient, user_factory, file_factory):
    from pathlib import Path
    from unittest import mock

    user = user_factory()
    file = file_factory(user.id)
    key = secrets.token_urlsafe()
    with mock.patch(
        "app.api.files.views.cache.get",
        mock.AsyncMock(return_value=Path(user.username) / file.path),
    ):
        response = client.login(user.id).get(f"/files/download?key={key}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "attachment/zip"
    assert response.content


def test_download_folder_with_files(client: TestClient, user_factory, file_factory):
    from pathlib import Path
    from unittest import mock

    user = user_factory()
    file_factory(user.id, path="a/b/c/d.txt")
    key = secrets.token_urlsafe()
    with mock.patch(
        "app.api.files.views.cache.get",
        mock.AsyncMock(return_value=Path(user.username) / "a"),
    ):
        response = client.login(user.id).get(f"/files/download?key={key}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "attachment/zip"
    assert response.content


def test_download_but_key_is_invalid(client: TestClient):
    key = secrets.token_urlsafe()
    response = client.get(f"/files/download?key={key}")
    assert response.status_code == 404
    assert response.json() == {
        "code": "DOWNLOAD_NOT_FOUND",
        "message": "Download not found.",
    }


def test_empty_trash(client: TestClient, user_factory):
    user = user_factory()
    response = client.login(user.id).post("/files/empty_trash")
    assert response.status_code == 200
    data = response.json()
    assert data.pop("id")
    assert data.pop("mtime")
    assert data == {
        "type": "folder",
        "name": "Trash",
        "path": "Trash",
        "size": 0,
        "hidden": True,
    }


def test_get_download_url(client: TestClient, user_factory, file_factory):
    user = user_factory()
    file = file_factory(user.id)
    payload = {"path": file.path}
    response = client.login(user.id).post("/files/get_download_url", json=payload)
    assert response.status_code == 200
    download_url = response.json()["download_url"]
    assert download_url.startswith(client.base_url)


def test_get_download_url_but_file_not_found(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "wrong/path"}
    response = client.login(user.id).post("/files/get_download_url", json=payload)
    assert response.json() == {
        "code": "PATH_NOT_FOUND",
        "message": "Path not found."
    }


def test_list_folder(client: TestClient, user_factory, file_factory):
    user = user_factory()
    file_factory(user.id, path="file.txt")
    file_factory(user.id, path="folder/file.txt")
    payload = {"path": "."}
    response = client.login(user.id).post("/files/list_folder", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "."
    assert data["count"] == 2
    assert data["items"][0]["name"] == "folder"
    assert data["items"][1]["name"] == "file.txt"


def test_list_folder_but_path_does_not_exists(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "wrong/path"}
    response = client.login(user.id).post("/files/list_folder", json=payload)
    assert response.json() == {
        "code": "PATH_NOT_FOUND",
        "message": "Path not found."
    }
