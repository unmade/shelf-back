from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest
from fastapi import Request

from app.api.sharing.schemas import FileMemberAccessLevel, SharedLinkFileSchema
from app.app.files.domain import File, FileMember

if TYPE_CHECKING:
    from app.app.files.domain.file_member import FileMemberActions


class TestFileMemberAccessLevel:
    @pytest.mark.parametrize(["given", "expected"], [
        (FileMemberAccessLevel.editor, FileMember.EDITOR),
        (FileMemberAccessLevel.viewer, FileMember.VIEWER),
    ])
    def test_as_actions(
        self, given: FileMemberAccessLevel, expected: FileMemberActions
    ):
        assert given.as_actions() == expected

    def test_as_actions_when_value_is_unsupported(self):
        with pytest.raises(AssertionError):
            FileMemberAccessLevel.owner.as_actions()


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
