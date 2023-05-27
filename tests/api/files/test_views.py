from __future__ import annotations

import secrets
import urllib.parse
import uuid
from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.api import shortcuts
from app.api.files.exceptions import (
    DownloadNotFound,
    FileAlreadyExists,
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
from app.app.files.domain import ContentMetadata, Exif, File, Path, mediatypes
from app.app.infrastructure.storage import ContentReader
from app.app.infrastructure.worker import Job, JobStatus
from app.app.users.domain import Account
from app.worker.jobs.files import ErrorCode as TaskErrorCode
from app.worker.jobs.files import FileTaskResult

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.api.exceptions import APIError
    from app.app.files.domain import AnyPath, Namespace
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


def _make_file(
    ns_path: AnyPath, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=str(ns_path),
        name=Path(path).name,
        path=path,
        size=size,
        mediatype=mediatype,
    )


def _make_content_reader(content: bytes, *, zipped: bool) -> ContentReader:
    async def content_iter():
        yield content

    return ContentReader(content_iter(), zipped=zipped)


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

    async def test_when_folder_exists(
        self, client: TestClient, namespace: Namespace, ns_use_case: MagicMock
    ):
        ns_path = namespace.path
        ns_use_case.create_folder.side_effect = File.AlreadyExists
        payload = {"path": "Trash"}
        client.mock_namespace(namespace)
        response = await client.post("/files/create_folder", json=payload)
        assert response.json() == FileAlreadyExists(path='Trash').as_dict()
        assert response.status_code == 400
        ns_use_case.create_folder.assert_awaited_once_with(ns_path, "Trash")

    async def test_when_parent_is_a_file(
        self, client: TestClient, namespace: Namespace, ns_use_case: MagicMock
    ):
        ns_use_case.create_folder.side_effect = File.NotADirectory()
        path = "file/folder"
        payload = {"path": path}
        client.mock_namespace(namespace)
        response = await client.post("/files/create_folder", json=payload)
        assert response.json() == NotADirectory(path="file/folder").as_dict()
        assert response.status_code == 400
        ns_use_case.create_folder.assert_awaited_once_with(namespace.path, path)


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
        content_reader = _make_content_reader(b"Hello, World!", zipped=False)
        ns_use_case.download.return_value = file, content_reader
        key = await shortcuts.create_download_cache(namespace.path, file.path)
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="f.txt"'
        assert response.headers["Content-Length"] == str(file.size)
        assert response.headers["Content-Type"] == "plain/text"
        assert response.content == b"Hello, World!"
        ns_use_case.download.assert_awaited_once_with(str(namespace.path), file.path)

    async def test_when_content_reader_is_zipped(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "f.txt")
        content_reader = _make_content_reader(b"Hello, World!", zipped=True)
        ns_use_case.download.return_value = file, content_reader
        key = await shortcuts.create_download_cache(namespace.path, file.path)
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        assert "Content-Length" not in response.headers
        assert response.headers["Content-Type"] == "attachment/zip"
        assert response.content == b"Hello, World!"
        ns_use_case.download.assert_awaited_once_with(str(namespace.path), file.path)

    async def test_when_path_has_non_latin_characters(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "ф.txt")
        content_reader = _make_content_reader(b"Hello, World!", zipped=False)
        ns_use_case.download.return_value = file, content_reader
        key = await shortcuts.create_download_cache(namespace.path, file.path)
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="ф.txt"'
        ns_use_case.download.assert_awaited_once_with(str(namespace.path), file.path)

    async def test_download_but_key_is_invalid(
        self, client: TestClient, ns_use_case: MagicMock
    ):
        key = secrets.token_urlsafe()
        response = await client.get(self.url(key))
        assert response.status_code == 404
        assert response.json() == DownloadNotFound().as_dict()
        ns_use_case.download.assert_not_awaited()

    async def test_download_but_file_not_found(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace
    ):
        # GIVEN
        path = "f.txt"
        key = await shortcuts.create_download_cache(namespace.path, path)
        ns_use_case.download.side_effect = File.NotFound
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(key))
        # THEN
        assert response.json() == PathNotFound(path=path).as_dict()
        assert response.status_code == 404
        ns_use_case.download.assert_awaited_once_with(str(namespace.path), path)


class TestDownloadXHR:
    url = "/files/download"

    # Use lambda to prevent long names in pytest output
    async def test(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "f.txt")
        content_reader = _make_content_reader(b"Hello, World!", zipped=False)
        ns_use_case.download.return_value = file, content_reader
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

    async def test_when_content_reader_is_zipped(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "f.txt")
        content_reader = _make_content_reader(b"Hello, World!", zipped=True)
        ns_use_case.download.return_value = file, content_reader
        payload = {"path": str(file.path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        assert "Content-Length" not in response.headers
        assert response.headers["Content-Type"] == "attachment/zip"
        assert response.content == b"Hello, World!"
        ns_use_case.download.assert_awaited_once_with(namespace.path, file.path)

    async def test_when_path_has_non_latin_characters(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        file = _make_file(str(namespace.path), "ф.txt")
        content_reader = _make_content_reader(b"Hello, World!", zipped=False)
        ns_use_case.download.return_value = file, content_reader
        payload = {"path": str(file.path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="ф.txt"'
        ns_use_case.download.assert_awaited_once_with(namespace.path, file.path)

    async def test_download_but_file_not_found(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace
    ):
        # GIVEN
        path = "f.txt"
        ns_use_case.download.side_effect = File.NotFound
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == PathNotFound(path=path).as_dict()
        assert response.status_code == 404
        ns_use_case.download.assert_awaited_once_with(namespace.path, path)


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
        ns_use_case.file.filecore.get_by_id_batch = mock.AsyncMock(return_value=files)
        payload = {"ids": [file.id for file in files]}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post("/files/get_batch", json=payload)
        # THEN
        ns_use_case.file.filecore.get_by_id_batch.assert_awaited_once_with(
            [uuid.UUID(id) for id in payload["ids"]]
        )
        assert response.json()["count"] == 2
        assert len(response.json()["items"]) == 2
        assert response.json()["items"][0]["id"] == files[0].id
        assert response.json()["items"][1]["id"] == files[1].id
        assert response.status_code == 200


class TestGetDownloadURL:
    url = "/files/get_download_url"

    async def test(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path, path = namespace.path, "f.txt"
        file = _make_file(ns_path, path)
        payload = {"path": str(file.path)}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        ns_use_case.get_item_at_path.assert_awaited_once_with(ns_path, path)
        download_url = response.json()["download_url"]
        assert download_url.startswith(str(client.base_url))
        assert response.status_code == 200
        parts = urllib.parse.urlsplit(download_url)
        qs = urllib.parse.parse_qs(parts.query)
        assert len(qs["key"]) == 1

    async def test_when_file_not_found(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        path = "wrong/path"
        ns_use_case.get_item_at_path.side_effect = File.NotFound
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json() == PathNotFound(path="wrong/path").as_dict()
        assert response.status_code == 404


class TestGetContentMetadata:
    url = "/files/get_content_metadata"

    async def test(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        file_id, path = str(uuid.uuid4()), "img.jpeg"
        exif = Exif(width=1280, height=800)
        metadata = ContentMetadata(file_id=file_id, data=exif)
        ns_use_case.get_file_metadata.return_value = metadata
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["file_id"] == file_id
        assert response.json()["data"] == exif.dict()
        assert response.status_code == 200
        ns_use_case.get_file_metadata.assert_awaited_once_with(namespace.path, path)

    async def test_when_file_has_no_metadata(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        path = "img.jpeg"
        ns_use_case.get_file_metadata.side_effect = ContentMetadata.NotFound
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post("/files/get_content_metadata", json=payload)
        # THEN
        assert response.json() == FileContentMetadataNotFound(path=path).as_dict()
        assert response.status_code == 404

    async def test_when_file_not_found(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        path = "wrong/path"
        ns_use_case.get_file_metadata.side_effect = File.NotFound
        payload = {"path": path}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post("/files/get_content_metadata", json=payload)
        # THEN
        assert response.json() == PathNotFound(path=path).as_dict()
        assert response.status_code == 404


class TestGetThumbnail:
    def url(self, file_id: str, *, size: str = "xs") -> str:
        return f"/files/get_thumbnail/{file_id}?size=xs"

    async def test(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
        image_content: BytesIO,
    ):
        # GIVEN
        path = "im.jpeg"
        file, thumbnail = _make_file(namespace.path, path), image_content.getvalue()
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
        image_content: BytesIO,
    ):
        # GIVEN
        path = "изо.jpeg"
        file, thumbnail = _make_file(namespace.path, path), image_content.getvalue()
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

    @pytest.mark.parametrize(["error", "expected_error_cls"], [
        (File.NotFound(), PathNotFound),
        (File.IsADirectory(), IsADirectory),
        (File.ThumbnailUnavailable(), ThumbnailUnavailable),
    ])
    async def test_reraising_app_errors_to_api_errors(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
        error,
        expected_error_cls,
    ):
        # GIVEN
        file_id = str(uuid.uuid4())
        ns_use_case.get_file_thumbnail.side_effect = error
        # WHEN
        client.mock_namespace(namespace)
        response = await client.get(self.url(file_id))
        # THEN
        assert response.status_code == expected_error_cls.status_code
        assert response.json() == expected_error_cls(path=file_id).as_dict()


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

    async def test_when_path_does_not_exists(
        self, client: TestClient, ns_use_case: MagicMock, namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        ns_use_case.list_folder.side_effect = File.NotFound
        payload = {"path": "wrong/path"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        ns_use_case.list_folder.assert_awaited_once_with(ns_path, payload["path"])
        assert response.status_code == 404
        assert response.json() == PathNotFound(path="wrong/path").as_dict()

    async def test_when_path_is_not_a_folder(
        self,
        client: TestClient,
        ns_use_case: MagicMock,
        namespace: Namespace,
    ):
        # GIVEN
        ns_path = namespace.path
        ns_use_case.list_folder.side_effect = File.NotADirectory
        payload = {"path": "f.txt"}
        # WHEN
        client.mock_namespace(namespace)
        response = await client.post(self.url, json=payload)
        # THEN
        ns_use_case.list_folder.assert_awaited_once_with(ns_path, payload["path"])
        assert response.json() == NotADirectory(path="f.txt").as_dict()


class TestMoveBatch:
    url = "/files/move_batch"

    async def test(
        self, client: TestClient, namespace: Namespace, worker_mock: MagicMock,
    ):
        # GIVEN
        context = mock.MagicMock()
        expected_job_id = str(uuid.uuid4())
        worker_mock.enqueue.return_value = Job(id=expected_job_id)
        payload = MoveBatchRequest.parse_obj({
            "items": [
                {"from_path": f"{i}.txt", "to_path": f"folder/{i}.txt"}
                for i in range(3)
            ]
        })
        client.mock_current_user_ctx(context).mock_namespace(namespace)
        # WHEN
        response = await client.post(self.url, json=payload.dict())
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
        assert isinstance(ns_use_case.add_file.await_args.args[2], SpooledTemporaryFile)

    @pytest.mark.parametrize(["path", "error", "expected_error"], [
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
        ns_use_case.add_file.side_effect = error
        payload = {
            "file": BytesIO(b"Dummy file"),
            "path": (None, path.encode()),
        }
        client.mock_namespace(namespace)
        response = await client.post(self.url, files=payload)  # type: ignore
        assert response.json() == expected_error.as_dict()
        assert response.status_code == 400
        ns_use_case.add_file.assert_awaited_once()
