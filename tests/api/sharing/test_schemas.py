from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

from fastapi import Request

from app.api.sharing.schemas import SharedLinkFileSchema
from app.app.files.domain import File, Path

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath


def _make_file(ns_path: str, path: AnyPath, mediatype: str = "plain/text") -> File:
    return File(
        id=uuid.uuid7(),
        owner_id=uuid.uuid7(),
        ns_path=ns_path,
        name=Path(path).name,
        path=Path(path),
        chash=uuid.uuid4().hex,
        size=10,
        mediatype=mediatype,
    )


class TestSharedLinkFileSchema:
    def test_make_thumbnail_url_with_arbitrary_file(self):
        # GIVEN
        file = _make_file("admin", "f.txt", mediatype="plain/text")
        token = "shared-link-token"
        request = mock.MagicMock(Request)

        # WHEN
        result = SharedLinkFileSchema._make_thumbnail_url(file, token, request)

        # THEN
        assert result is None
        request.url_for.assert_not_called()

    def test_make_thumbnail_url_with_image(self):
        # GIVEN
        file = _make_file("admin", "im.jpeg", mediatype="image/jpeg")
        token = "shared-link-token"
        request = mock.MagicMock(Request)

        # WHEN
        result = SharedLinkFileSchema._make_thumbnail_url(file, token, request)

        # THEN
        assert result == str(request.url_for.return_value)
        request.url_for.assert_called_once_with(
            "get_shared_link_thumbnail", token=token
        )
