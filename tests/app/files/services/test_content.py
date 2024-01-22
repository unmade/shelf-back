from __future__ import annotations

import uuid
from typing import IO, TYPE_CHECKING, AsyncIterator, cast
from unittest import mock

import pytest

from app.app.files.domain import File, Path
from app.config import config

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath, IFileContent
    from app.app.files.services import ContentService

pytestmark = [pytest.mark.anyio]


async def _aiter(content: IO[bytes]) -> AsyncIterator[bytes]:
    for chunk in content:
        yield chunk


def _make_file(
    ns_path: str, path: AnyPath, size: int = 10, mediatype: str = "image/jpeg"
) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=Path(path).name,
        path=Path(path),
        chash=uuid.uuid4().hex,
        size=size,
        mediatype=mediatype,
    )


class TestProcess:
    async def test(self, content_service: ContentService, content: IFileContent):
        # GIVEN
        file, chunks = _make_file("admin", "im.jpeg"), _aiter(content.file)
        dupefinder = cast(mock.MagicMock, content_service.dupefinder)
        filecore = cast(mock.MagicMock, content_service.filecore)
        filecore.download.return_value = file, chunks
        metadata = cast(mock.MagicMock, content_service.metadata)
        thumbnailer = cast(mock.MagicMock, content_service.thumbnailer)
        # WHEN
        await content_service.process(file.id)
        # THEN
        dupefinder.track.assert_awaited_once()
        metadata.track.assert_awaited_once()
        thumbnailer.generate_thumbnails.assert_awaited_once_with(
            file.id, sizes=config.features.pre_generated_thumbnail_sizes
        )


class TestProcessAsync:
    async def test(self, content_service: ContentService):
        # GIVEN
        file_id = uuid.uuid4()
        worker = cast(mock.MagicMock, content_service.worker)
        # WHEN
        await content_service.process_async(file_id)
        # THEN
        worker.enqueue.assert_awaited_once_with("process_file_content", file_id=file_id)


class TestReindexContents:
    async def test(self, content_service: ContentService, image_content: IFileContent):
        # GIVEN
        ns_path = "admin"
        txt = _make_file(ns_path, "f.txt", mediatype="plain/text")
        jpg_1 = _make_file(ns_path, "a/b/img (1).jpeg", mediatype="image/jpeg")
        jpg_2 = _make_file(ns_path, "a/b/img (2).jpeg", mediatype="image/jpeg")

        async def iter_files_result():
            yield [txt]
            yield [jpg_1]
            yield [jpg_2]

        filecore = cast(mock.MagicMock, content_service.filecore)
        filecore.iter_files.return_value = iter_files_result()
        filecore.download.side_effect = [
            (txt, _aiter(image_content.file)),
            (jpg_1, _aiter(image_content.file)),
            (jpg_2, _aiter(image_content.file)),
        ]
        dupefinder = cast(mock.MagicMock, content_service.dupefinder)
        meta_service = cast(mock.MagicMock, content_service.metadata)

        # WHEN
        await content_service.reindex_contents(ns_path)

        # THEN
        filecore.iter_files.assert_called_once()
        dupefinder_tracker = dupefinder.track_batch.return_value.__aenter__.return_value
        assert len(dupefinder_tracker.mock_calls) == 2
        metadata_tracker = meta_service.track_batch.return_value.__aenter__.return_value
        assert len(metadata_tracker.mock_calls) == 2
        chasher = filecore.chash_batch.return_value.__aenter__.return_value
        assert len(chasher.mock_calls) == 3
