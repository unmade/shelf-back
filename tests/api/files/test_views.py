from __future__ import annotations

import secrets
import urllib.parse
import uuid
from io import BytesIO
from typing import TYPE_CHECKING, AsyncIterator
from unittest import mock

import pytest
from starlette.datastructures import UploadFile

from app.api import shortcuts
from app.api.files.exceptions import (
    DownloadNotFound,
    FileActionNotAllowed,
    FileContentMetadataNotFound,
    IsADirectory,
    MalformedPath,
    NotADirectory,
    PathNotFound,
    StorageQuotaExceeded,
    ThumbnailUnavailable,
    UploadFileTooLarge,
)
from app.api.files.schemas import MoveBatchRequest
from app.app.files.domain import (
    ContentMetadata,
    Exif,
    File,
    MountedFile,
    MountPoint,
    Path,
    mediatypes,
)
from app.app.infrastructure.worker import Job, JobStatus
from app.app.users.domain import Account
from app.worker.jobs.files import ErrorCode as TaskErrorCode
from app.worker.jobs.files import FileTaskResult

if TYPE_CHECKING:
    from unittest.mock import MagicMock
    from uuid import UUID

    from app.api.exceptions import APIError
    from app.app.files.domain import AnyPath, IFileContent, Namespace
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]

_FILE_ID = uuid.uuid4()


def _make_file(
    ns_path: AnyPath, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=str(ns_path),
        name=Path(path).name,
        path=Path(path),
        chash=uuid.uuid4().hex,
        size=size,
        mediatype=mediatype,
    )


async def _aiter(content: bytes) -> AsyncIterator[bytes]:
    yield content


class TestCreateFolder:
    @pytest.mark.parametrize(["path", "expected_path"], [
        ("Folder", "Folder"),
        ("Nested/Path/Folder", "Nested/Path/Folder",),
        (".Hidden Folder", ".Hidden Folder",),
        (" Whitespaces ", "Whitespaces",),
    ])
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        expected_path: str,
    ):
        # GIVEN
        folder = _make_file(
            ns_path=str(namespace.path),
            path=expected_path,
            size=0,
            mediatype=mediatypes.FOLDER,
        )
        ns_use_case.create_folder.return_value = folder
        payload = {"path": str(path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post("/files/create_folder", json=payload)
        # THEN
        assert response.json()["id"] == str(folder.id)
        assert response.json()["name"] == folder.name
        assert response.json()["path"] == folder.path
        assert response.status_code == 200
        ns_use_case.create_folder.assert_awaited_once_with(
            namespace.path, expected_path
        )

    @pytest.mark.parametrize(["path", "expected_error"], [
        ("Trash", MalformedPath("Path 'Trash' is a special path and can't be created")),
        ("Trash/folder", MalformedPath("Can't create folders in the Trash")),
    ])
    async def test_when_creating_in_special_path(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        expected_error: APIError,
    ):
        # GIVEN
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post("/files/create_folder", json=payload)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code
        ns_use_case.create_folder.assert_not_awaited()

    @pytest.mark.parametrize(["path", "error", "expected_error"], [
        ("teamfolder/f.txt", File.ActionNotAllowed(), FileActionNotAllowed()),
        ("file/folder", File.NotADirectory(), NotADirectory(path="file/folder")),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        ns_path = namespace.path
        ns_use_case.create_folder.side_effect = error
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post("/files/create_folder", json=payload)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code
        ns_use_case.create_folder.assert_awaited_once_with(ns_path, path)


class TestDeleteImmediatelyBatch:
    url = "/files/delete_immediately_batch"

    async def test(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock
    ):
        # GIVEN
        expected_job_id = str(uuid.uuid4())
        worker_mock.enqueue.return_value = Job(id=expected_job_id)
        payload = {
            "items": [
                {"path": f"{i}.txt"} for i in range(3)
            ]
        }
        client.mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        job_id = response.json()["async_task_id"]
        assert job_id == str(expected_job_id)
        assert response.status_code == 200
        paths = [f"{i}.txt" for i in range(3)]
        worker_mock.enqueue.assert_awaited_once_with(
            "delete_immediately_batch", namespace.path, paths
        )

    @pytest.mark.parametrize("path", [".", "Trash"])
    async def test_when_path_is_malformed(
        self, client: TestClient, namespace: Namespace, path: str
    ):
        # GIVEN
        payload = {"items": [{"path": path}]}
        client.mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        message = f"Path '{path}' is a special path and can't be deleted"
        assert response.json() == MalformedPath(message).as_dict()
        assert response.status_code == 400


class TestDeleteImmediatelyBatchCheck:
    url = "/files/delete_immediately_batch/check"

    async def test_when_job_is_pending(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock,
    ):
        # GIVEN
        job_id = str(uuid.uuid4())
        payload = {"async_task_id": job_id}
        client.mock_namespace(namespace)
        worker_mock.get_status.return_value = JobStatus.pending
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["status"] == "pending"
        assert response.json()["result"] is None
        assert response.status_code == 200
        worker_mock.get_status.assert_awaited_once_with(job_id)

    async def test_when_job_is_completed(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock
    ):
        # GIVEN
        ns_path = str(namespace.path)
        job_id = str(uuid.uuid4())
        worker_mock.get_status.return_value = JobStatus.complete
        worker_mock.get_result.return_value = [
            FileTaskResult(file=_make_file(ns_path, "f.txt"), err_code=None),
            FileTaskResult(file=None, err_code=TaskErrorCode.file_not_found),
        ]
        payload = {"async_task_id": job_id}
        client.mock_namespace(namespace)

        # WHEN
        response = await client.post(self.url, json=payload)

        # THEN
        assert response.json()["status"] == "completed"
        results = response.json()["result"]
        assert len(results) == 2

        assert results[0]["file"]["path"] == "f.txt"
        assert results[0]["err_code"] is None

        assert results[1]["file"] is None
        assert results[1]["err_code"] == "file_not_found"

        assert response.status_code == 200
        worker_mock.get_status.assert_awaited_once_with(job_id)
        worker_mock.get_result.assert_awaited_once_with(job_id)


class TestDownload:
    def url(self, key: str) -> str:
        return f"/files/download?key={key}"

    async def test(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "f.txt")
        ns_use_case.download_by_id.return_value = _aiter(b"Hello, World!")
        key = await shortcuts.create_download_cache(file)
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="f.txt"'
        assert response.headers["Content-Length"] == str(file.size)
        assert response.headers["Content-Type"] == "plain/text"
        assert response.content == b"Hello, World!"
        ns_use_case.download_by_id.assert_awaited_once_with(file.id)

    async def test_when_path_has_non_latin_characters(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "ф.txt")
        ns_use_case.download_by_id.return_value = _aiter(b"Hello, World!")
        key = await shortcuts.create_download_cache(file)
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="ф.txt"'
        ns_use_case.download_by_id.assert_awaited_once_with(file.id)

    async def test_download_but_key_is_invalid(
        self, client: TestClient, ns_use_case: MagicMock
    ):
        key = secrets.token_urlsafe()
        response = await client.get(self.url(key))
        assert response.status_code == 404
        assert response.json() == DownloadNotFound().as_dict()
        ns_use_case.download_by_id.assert_not_awaited()

    @pytest.mark.parametrize(["path", "error", "expected_error"], [
        ("folder", File.IsADirectory(), IsADirectory(path="folder")),
        ("f.txt", File.NotFound(), PathNotFound(path="f.txt")),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        file = _make_file(namespace.path, path)
        key = await shortcuts.create_download_cache(file)
        ns_use_case.download_by_id.side_effect = error
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(key))
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code
        ns_use_case.download_by_id.assert_awaited_once_with(file.id)


class TestDownloadXHR:
    url = "/files/download"

    async def test(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "f.txt")
        ns_use_case.download.return_value = file, _aiter(b"Hello, World!")
        payload = {"path": str(file.path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="f.txt"'
        assert response.headers["Content-Length"] == str(file.size)
        assert response.headers["Content-Type"] == "plain/text"
        assert response.content == b"Hello, World!"
        ns_use_case.download.assert_awaited_once_with(namespace.path, file.path)

    async def test_when_path_has_non_latin_characters(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "ф.txt")
        ns_use_case.download.return_value = file, _aiter(b"Hello, World!")
        payload = {"path": str(file.path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="ф.txt"'
        ns_use_case.download.assert_awaited_once_with(namespace.path, file.path)

    @pytest.mark.parametrize(["path", "error", "expected_error"], [
        ("teamfolder/f.txt", File.ActionNotAllowed(), FileActionNotAllowed()),
        ("folder", File.IsADirectory(), IsADirectory(path="folder")),
        ("f.txt", File.NotFound(), PathNotFound(path="f.txt")),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        ns_use_case.download.side_effect = error
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code
        ns_use_case.download.assert_awaited_once_with(namespace.path, path)


class TestDownloadFolder:
    def url(self, key: str) -> str:
        return f"/files/download_folder?key={key}"

    async def test(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(namespace.path, "f", mediatype=mediatypes.FOLDER)
        ns_use_case.download_folder.return_value = BytesIO(b"I'm a ZIP archive")
        key = await shortcuts.create_download_cache(file)
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="f.zip"'
        assert "Content-Length" not in response.headers
        assert response.content == b"I'm a ZIP archive"
        ns_use_case.download_folder.assert_called_once_with(namespace.path, file.path)


class TestEmptyTrash:
    url = "/files/empty_trash"

    async def test(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock
    ):
        # GIVEN
        context = mock.MagicMock()
        expected_job_id = str(uuid.uuid4())
        worker_mock.enqueue.return_value = Job(id=expected_job_id)
        client.mock_current_user_ctx(context).mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url)
        # THEN
        job_id = response.json()["async_task_id"]
        assert job_id == str(expected_job_id)
        assert response.status_code == 200
        worker_mock.enqueue.assert_awaited_once_with(
            "empty_trash", namespace.path, context=context
        )


class TestEmptyTrashCheck:
    url = "/files/empty_trash/check"

    async def test_when_job_is_pending(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock
    ):
        # GIVEN
        job_id = str(uuid.uuid4())
        payload = {"async_task_id": job_id}
        client.mock_namespace(namespace)
        worker_mock.get_status.return_value = JobStatus.pending
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["status"] == "pending"
        assert response.json()["result"] is None
        assert response.status_code == 200
        worker_mock.get_status.assert_awaited_once_with(job_id)

    async def test_when_job_is_completed(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock
    ):
        # GIVEN
        job_id = str(uuid.uuid4())
        payload = {"async_task_id": job_id}
        client.mock_namespace(namespace)
        worker_mock.get_status.return_value = JobStatus.complete
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["status"] == "completed"
        assert response.json()["result"] is None
        assert response.status_code == 200
        worker_mock.get_status.assert_awaited_once_with(job_id)


class TestFindDuplicates:
    url = "/files/find_duplicates"

    async def test(
        self, client: TestClient, namespace: Namespace, ns_use_case: MagicMock
    ):
        # GIVEN
        ns_path = namespace.path
        files = [_make_file(str(ns_path), f"{idx}.txt") for idx in range(4)]
        ns_use_case.find_duplicates.return_value = [
            [files[0], files[2]], [files[1], files[3]]
        ]
        payload = {"path": "."}
        client.mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["path"] == "."
        assert response.json()["count"] == 2
        assert len(response.json()["items"][0]) == 2
        assert len(response.json()["items"][1]) == 2
        ns_use_case.find_duplicates.assert_awaited_once_with(ns_path, ".", 5)

    async def test_when_result_is_empty(
        self, client: TestClient, namespace: Namespace, ns_use_case: MagicMock
    ):
        # GIVEN
        ns_path = namespace.path
        ns_use_case.find_duplicates.return_value = []
        payload = {"path": "."}
        client.mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["path"] == "."
        assert response.json()["count"] == 0
        ns_use_case.find_duplicates.assert_awaited_once_with(ns_path, ".", 5)


class TestGetBatch:
    async def test(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        files = [
            _make_file(namespace.path, f"{idx}.txt")
            for idx in range(2)
        ]
        ns_use_case.file.get_by_id_batch = mock.AsyncMock(return_value=files)
        payload = {"ids": [str(file.id) for file in files]}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post("/files/get_batch", json=payload)
        # THEN
        ns_use_case.file.get_by_id_batch.assert_awaited_once_with(
            namespace.path, [uuid.UUID(id) for id in payload["ids"]]
        )
        assert response.json()["count"] == 2
        assert len(response.json()["items"]) == 2
        assert response.json()["items"][0]["id"] == str(files[0].id)
        assert response.json()["items"][1]["id"] == str(files[1].id)
        assert response.status_code == 200


class TestGetDownloadURL:
    url = "/files/get_download_url"

    async def test_on_file(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(namespace.path, "f.txt")
        ns_use_case.get_item_at_path.return_value = file
        payload = {"path": str(file.path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        ns_use_case.get_item_at_path.assert_awaited_once_with(file.ns_path, file.path)
        download_url = response.json()["download_url"]
        assert download_url.startswith(str(client.base_url))
        assert "/download?" in download_url
        assert response.status_code == 200
        parts = urllib.parse.urlsplit(download_url)
        qs = urllib.parse.parse_qs(parts.query)
        assert len(qs["key"]) == 1

    async def test_on_folder(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(namespace.path, "f", mediatype=mediatypes.FOLDER)
        ns_use_case.get_item_at_path.return_value = file
        payload = {"path": str(file.path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        ns_use_case.get_item_at_path.assert_awaited_once_with(file.ns_path, file.path)
        download_url = response.json()["download_url"]
        assert download_url.startswith(str(client.base_url))
        assert "/download_folder?" in download_url
        assert response.status_code == 200
        parts = urllib.parse.urlsplit(download_url)
        qs = urllib.parse.parse_qs(parts.query)
        assert len(qs["key"]) == 1

    async def test_when_mounted_file_is_not_permitted_to_download(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(namespace.path, "f.txt")
        mounted_file = MountedFile(
            **file.model_dump(),
            mount_point=MountPoint(
                source=MountPoint.Source(ns_path="user", path=Path("f.txt")),
                folder=MountPoint.ContainingFolder(ns_path="admin", path=Path(".")),
                display_name="f.txt",
                actions=MountPoint.Actions(can_download=False),
            ),
        )
        ns_use_case.get_item_at_path.return_value = mounted_file
        payload = {"path": str(mounted_file.path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == FileActionNotAllowed().as_dict()
        assert response.status_code == FileActionNotAllowed.status_code
        ns_use_case.get_item_at_path.assert_awaited_once_with(file.ns_path, file.path)

    @pytest.mark.parametrize(["path", "error", "expected_error"], [
        ("teamfolder/f.txt", File.ActionNotAllowed(), FileActionNotAllowed()),
        ("path/not/found", File.NotFound(), PathNotFound(path="path/not/found")),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        ns_use_case.get_item_at_path.side_effect = error
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code


class TestGetContentMetadata:
    url = "/files/get_content_metadata"

    async def test(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        exif = Exif(width=1280, height=800)
        metadata = ContentMetadata(file_id=file_id, data=exif)
        ns_use_case.get_file_metadata.return_value = metadata
        payload = {"id": str(file_id)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["file_id"] == str(file_id)
        assert response.json()["data"] == exif.model_dump()
        assert response.status_code == 200
        ns_use_case.get_file_metadata.assert_awaited_once_with(namespace.path, file_id)

    @pytest.mark.parametrize(["error", "expected_error_cls"], [
        (ContentMetadata.NotFound, FileContentMetadataNotFound),
        (File.ActionNotAllowed(), FileActionNotAllowed),
        (File.NotFound(), PathNotFound),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        error: Exception,
        expected_error_cls: APIError,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        ns_use_case.get_file_metadata.side_effect = error
        payload = {"id": str(file_id)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["code"] == expected_error_cls.code
        assert response.status_code == expected_error_cls.status_code


class TestGetThumbnail:
    def url(self, file_id: UUID, *, size: str = "xs") -> str:
        return f"/files/get_thumbnail/{file_id}?size={size}"

    async def test(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
        image_content: IFileContent,
    ):
        # GIVEN
        ns_path, path = namespace.path, "im.jpeg"
        file, thumbnail = _make_file(ns_path, path), image_content.file.read()
        ns_use_case.get_file_thumbnail.return_value = file, thumbnail
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(file.id))
        # THEN
        assert response.content
        headers = response.headers
        assert response.status_code == 200
        assert headers["Content-Disposition"] == 'inline; filename="im.jpeg"'
        assert headers["Content-Length"] == '1651'
        assert headers["Content-Type"] == "image/webp"
        assert headers["Cache-Control"] == "private, max-age=31536000, no-transform"
        ns_use_case.get_file_thumbnail.assert_awaited_once_with(
            namespace.path, file.id, size=64
        )

    async def test_when_path_has_non_latin_characters(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
        image_content: IFileContent,
    ):
        # GIVEN
        ns_path, path = namespace.path, "изо.jpeg"
        file, thumbnail = _make_file(ns_path, path), image_content.file.read()
        ns_use_case.get_file_thumbnail.return_value = file, thumbnail
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(file.id))
        # THEN
        assert response.content
        headers = response.headers
        assert response.status_code == 200
        assert headers["Content-Disposition"] == 'inline; filename="изо.jpeg"'
        ns_use_case.get_file_thumbnail.assert_awaited_once_with(
            namespace.path, file.id, size=64
        )

    @pytest.mark.parametrize(["error", "expected_error"], [
        (File.ActionNotAllowed(), FileActionNotAllowed()),
        (File.NotFound(), PathNotFound(path=str(_FILE_ID))),
        (File.IsADirectory(), IsADirectory(path=str(_FILE_ID))),
        (File.ThumbnailUnavailable(), ThumbnailUnavailable(path=str(_FILE_ID))),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        file_id = _FILE_ID
        ns_use_case.get_file_thumbnail.side_effect = error
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(file_id))
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code


class TestListFolder:
    url = "/files/list_folder"

    async def test(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        files = [
            _make_file(ns_path, "folder", mediatype="application/directory"),
            _make_file(ns_path, "f.txt"),
            _make_file(ns_path, "im.jpeg", mediatype="image/jpeg"),
        ]
        ns_use_case.list_folder.return_value = files
        payload = {"path": "."}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        ns_use_case.list_folder.assert_awaited_once_with(ns_path, payload["path"])
        assert response.status_code == 200
        assert response.json()["path"] == "."
        assert response.json()["count"] == 3
        assert response.json()["items"][0]["name"] == "folder"
        assert response.json()["items"][0]["thumbnail_url"] is None
        assert response.json()["items"][1]["name"] == "f.txt"
        assert response.json()["items"][1]["thumbnail_url"] is None
        assert response.json()["items"][2]["name"] == "im.jpeg"
        assert response.json()["items"][2]["thumbnail_url"] is not None

    @pytest.mark.parametrize(["path", "error", "expected_error"], [
        ("teamfolder/f.txt", File.ActionNotAllowed(), FileActionNotAllowed()),
        ("f.txt", File.NotADirectory(), NotADirectory(path="f.txt")),
        ("path/not/found", File.NotFound(), PathNotFound(path="path/not/found")),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        ns_path = namespace.path
        ns_use_case.list_folder.side_effect = error
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        ns_use_case.list_folder.assert_awaited_once_with(ns_path, payload["path"])
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code


class TestMoveBatch:
    url = "/files/move_batch"

    async def test(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock,
    ):
        # GIVEN
        context = mock.MagicMock()
        expected_job_id = str(uuid.uuid4())
        worker_mock.enqueue.return_value = Job(id=expected_job_id)
        payload = MoveBatchRequest.model_validate({
            "items": [
                {"from_path": f"{i}.txt", "to_path": f"folder/{i}.txt"}
                for i in range(3)
            ]
        })
        client.mock_current_user_ctx(context).mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload.model_dump())
        # THEN
        job_id = response.json()["async_task_id"]
        assert job_id == str(expected_job_id)
        assert response.status_code == 200
        worker_mock.enqueue.assert_awaited_once_with(
            "move_batch", namespace.path, payload.items, context=context
        )


class TestMoveBatchCheck:
    url = "/files/move_batch/check"

    async def test_when_job_is_pending(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock
    ):
            # GIVEN
        job_id = str(uuid.uuid4())
        payload = {"async_task_id": job_id}
        client.mock_namespace(namespace)
        worker_mock.get_status.return_value = JobStatus.pending
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["status"] == "pending"
        assert response.json()["result"] is None
        assert response.status_code == 200
        worker_mock.get_status.assert_awaited_once_with(job_id)

    async def test_when_job_is_completed(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock
    ):
        # GIVEN
        ns_path = str(namespace.path)
        job_id = str(uuid.uuid4())
        worker_mock.get_status.return_value = JobStatus.complete
        worker_mock.get_result.return_value = [
            FileTaskResult(file=_make_file(ns_path, "f.txt"), err_code=None),
            FileTaskResult(file=None, err_code=TaskErrorCode.file_not_found),
        ]
        payload = {"async_task_id": job_id}
        client.mock_namespace(namespace)

        # WHEN
        response = await client.post(self.url, json=payload)

        # THEN
        assert response.json()["status"] == 'completed'
        results = response.json()["result"]
        assert len(results) == 2

        assert results[0]["file"]["path"] == "f.txt"
        assert results[0]["err_code"] is None

        assert results[1]["file"] is None
        assert results[1]["err_code"] == "file_not_found"

        assert response.status_code == 200
        worker_mock.get_status.assert_awaited_once_with(job_id)
        worker_mock.get_result.assert_awaited_once_with(job_id)


class TestMoveToTrashBatch:
    url = "/files/move_to_trash_batch"

    async def test(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock,
    ):
        # GIVEN
        context = mock.MagicMock()
        expected_job_id = str(uuid.uuid4())
        worker_mock.enqueue.return_value = Job(id=expected_job_id)
        payload = {
            "items": [
                {"path": f"{i}.txt"} for i in range(3)
            ]
        }
        client.mock_current_user_ctx(context).mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload)
        # THEN
        job_id = response.json()["async_task_id"]
        assert job_id == str(expected_job_id)
        assert response.status_code == 200
        paths = [item["path"] for item in payload["items"]]
        worker_mock.enqueue.assert_awaited_once_with(
            "move_to_trash_batch", namespace.path, paths, context=context
        )


class TestUpload:
    url = "/files/upload"

    @pytest.mark.parametrize(["path", "expected_path"], [
        (b"folder/file.txt", "folder/file.txt"),
        (b"./f.txt", "f.txt"),
    ])
    async def test(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        expected_path: str,
    ):
        # GIVEN
        ns_path = str(namespace.path)
        content = BytesIO(b"Dummy file")
        size = len(content.getvalue())
        ns_use_case.add_file.return_value = _make_file(
            ns_path, expected_path, size=size
        )
        payload = {
            "file": content,
            "path": (None, path),
        }
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, files=payload)  # type: ignore
        # THEN
        assert response.status_code == 200
        assert response.json()["path"] == expected_path
        assert ns_use_case.add_file.await_args is not None
        assert len(ns_use_case.add_file.await_args.args) == 3
        assert ns_use_case.add_file.await_args.args[:2] == (ns_path, expected_path)
        assert isinstance(ns_use_case.add_file.await_args.args[2], UploadFile)

    @pytest.mark.parametrize(["path", "error", "expected_error"], [
        ("folder/f.txt", File.ActionNotAllowed(), FileActionNotAllowed()),
        ("Trash", File.MalformedPath("Bad path"), MalformedPath("Bad path")),
        ("f.txt/file", File.NotADirectory(), NotADirectory(path="f.txt/file")),
        ("f.txt", File.TooLarge(), UploadFileTooLarge()),
        ("f.txt", Account.StorageQuotaExceeded(), StorageQuotaExceeded()),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        namespace: Namespace,
        ns_use_case: MagicMock,
        path: str,
        error: Exception,
        expected_error: APIError,
    ):
        # GIVEN
        ns_use_case.add_file.side_effect = error
        payload = {
            "file": BytesIO(b"Dummy file"),
            "path": (None, path.encode()),
        }
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, files=payload)  # type: ignore
        # THEN
        assert response.json() == expected_error.as_dict()
        assert response.status_code == expected_error.status_code
        ns_use_case.add_file.assert_awaited_once()
