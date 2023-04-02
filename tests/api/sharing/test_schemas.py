from __future__ import annotations

from unittest import mock

from fastapi import Request

from app.api.sharing.schemas import SharedLinkFileSchema
from app.app.files.domain.file import File


class TestSharedLinkFileSchema:
    def test_make_thumbnail_url_with_image(self):
        # GIVEN
        file = mock.MagicMock(File, mediatype="image/jpeg")
        token = "shared-link-token"
        request = mock.MagicMock(Request)
        # WHEN
        result = SharedLinkFileSchema._make_thumbnail_url(file, token, request)
        # THEN
        assert result == str(request.url_for.return_value)
        request.url_for.assert_called_once_with(
            "get_shared_link_thumbnail", token=token
        )

    def test_make_thumbnail_url_with_arbitrary_file(self):
        # GIVEN
        file = mock.MagicMock(File, mediatype="plain/text")
        token = "shared-link-token"
        request = mock.MagicMock(Request)
        # WHEN
        result = SharedLinkFileSchema._make_thumbnail_url(file, token, request)
        # THEN
        assert result is None
        request.url_for.assert_not_called()
