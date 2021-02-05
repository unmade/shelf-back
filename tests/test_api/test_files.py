from __future__ import annotations

import secrets
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from app.api.files.exceptions import (
    AlreadyDeleted,
    AlreadyExists,
    DownloadNotFound,
    InvalidOperation,
    PathNotFound,
)

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
    assert response.json()["name"] == name
    assert response.json()["path"] == (expected_path or path)
    assert response.json()["hidden"] is hidden


def test_create_folder_but_folder_already_exists(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "Trash"}
    response = client.login(user.id).post("/files/create_folder", json=payload)
    assert response.status_code == 400
    assert response.json() == AlreadyExists().as_dict()


def test_delete_immediately(client: TestClient, user_factory):
    user = user_factory()
    name = path = "Test Folder"
    payload = {"path": path}
    client.login(user.id)
    client.post("/files/create_folder", json=payload)
    response = client.post("/files/delete_immediately", json=payload)
    assert response.status_code == 200
    assert response.json()["name"] == name
    assert response.json()["path"] == path


def test_delete_immediately_but_path_not_found(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "Test Folder"}
    response = client.login(user.id).post("/files/delete_immediately", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound().as_dict()


@pytest.mark.parametrize("path", [".", "Trash"])
def test_delete_immediately_but_it_is_a_special_folder(
    client: TestClient, user_factory, path,
):
    user = user_factory()
    payload = {"path": path}
    response = client.login(user.id).post("/files/delete_immediately", json=payload)
    assert response.status_code == 400
    assert response.json() == InvalidOperation().as_dict()


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
    assert response.json() == DownloadNotFound().as_dict()


def test_empty_trash(client: TestClient, user_factory):
    user = user_factory()
    response = client.login(user.id).post("/files/empty_trash")
    assert response.status_code == 200
    assert response.json()["path"] == "Trash"


def test_get_download_url(client: TestClient, user_factory, file_factory):
    user = user_factory()
    file = file_factory(user.id)
    payload = {"path": file.path}
    response = client.login(user.id).post("/files/get_download_url", json=payload)
    assert response.status_code == 200
    assert response.json()["download_url"].startswith(client.base_url)


def test_get_download_url_but_file_not_found(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "wrong/path"}
    response = client.login(user.id).post("/files/get_download_url", json=payload)
    assert response.json() == PathNotFound().as_dict()


def test_list_folder(client: TestClient, user_factory, file_factory):
    user = user_factory()
    file_factory(user.id, path="file.txt")
    file_factory(user.id, path="folder/file.txt")
    payload = {"path": "."}
    response = client.login(user.id).post("/files/list_folder", json=payload)
    assert response.status_code == 200
    assert response.json()["path"] == "."
    assert response.json()["count"] == 2
    assert response.json()["items"][0]["name"] == "folder"
    assert response.json()["items"][1]["name"] == "file.txt"


def test_list_folder_but_path_does_not_exists(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "wrong/path"}
    response = client.login(user.id).post("/files/list_folder", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound().as_dict()


@pytest.mark.parametrize(["from_path", "to_path"], [
    ("{name}", "folder/{name}"),
    ("folder/{name}", "{name}"),
    ("{name}", ".{name}"),
])
def test_move(client: TestClient, user_factory, file_factory, from_path, to_path):
    name = "file.txt"
    from_path = from_path.format(name=name)
    to_path = to_path.format(name=name)
    user = user_factory()
    file_factory(user.id, path=from_path)
    payload = {"from_path": from_path, "to_path": to_path}
    response = client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 200
    assert response.json()["type"] == "file"
    assert response.json()["path"] == to_path


@pytest.mark.parametrize("from_path", [".", "Trash"])
def test_move_but_it_is_a_special_path(
    client: TestClient, user_factory, file_factory, from_path,
):
    user = user_factory()
    payload = {"from_path": from_path, "to_path": "Trashbin"}
    response = client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 400
    assert response.json() == InvalidOperation().as_dict()


@pytest.mark.parametrize("to_path", [".", "Trash"])
def test_move_but_to_a_special_path(
    client: TestClient, user_factory, file_factory, to_path,
):
    user = user_factory()
    file = file_factory(user.id)
    payload = {"from_path": file.path, "to_path": to_path}
    response = client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 400
    assert response.json() == InvalidOperation().as_dict()


def test_move_but_file_not_found(client: TestClient, user_factory):
    user = user_factory()
    payload = {"from_path": "file_a.txt", "to_path": "file_b.txt"}
    response = client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound().as_dict()


def test_move_but_file_already_exists(client: TestClient, user_factory, file_factory):
    user = user_factory()
    file_a = file_factory(user.id, path="folder/file.txt")
    file_b = file_factory(user.id, path="file.txt")
    payload = {"from_path": file_a.path, "to_path": file_b.path}
    response = client.login(user.id).post("/files/move", json=payload)
    assert response.status_code == 400
    assert response.json() == AlreadyExists().as_dict()


@pytest.mark.parametrize(["file_path", "path", "expected_path"], [
    ("file.txt", "file.txt", "Trash/file.txt"),  # move file to trash
    ("a/b/c/d.txt", "a/b", "Trash/b"),  # move folder to trash
])
def test_move_to_trash(
    client: TestClient, user_factory, file_factory, file_path, path, expected_path,
):
    user = user_factory()
    file_factory(user.id, path=file_path)
    payload = {"path": path}
    response = client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 200
    assert response.json()["path"] == expected_path


def test_move_to_trash_but_it_is_a_trash(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "Trash"}
    response = client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 400
    assert response.json() == InvalidOperation().as_dict()


def test_move_to_trash_but_file_is_in_trash(
    client: TestClient, user_factory, file_factory,
):
    user = user_factory()
    file = file_factory(user.id, path="Trash/file.txt")
    payload = {"path": file.path}
    response = client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 400
    assert response.json() == AlreadyDeleted().as_dict()


def test_move_to_trash_but_file_not_found(client: TestClient, user_factory):
    user = user_factory()
    payload = {"path": "file.txt"}
    response = client.login(user.id).post("/files/move_to_trash", json=payload)
    assert response.status_code == 404
    assert response.json() == PathNotFound().as_dict()


def test_upload(client: TestClient, user_factory):
    user = user_factory()
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, "folder/file.txt"),
    }
    response = client.login(user.id).post("/files/upload", files=payload)
    assert response.status_code == 200
    assert response.json()["file"]["path"] == "folder/file.txt"
    assert len(response.json()["updates"]) == 2


def test_upload_but_to_a_special_path(client: TestClient, user_factory):
    user = user_factory()
    payload = {
        "file": BytesIO(b"Dummy file"),
        "path": (None, "Trash"),
    }
    response = client.login(user.id).post("/files/upload", files=payload)
    assert response.status_code == 400
    assert response.json() == InvalidOperation().as_dict()
