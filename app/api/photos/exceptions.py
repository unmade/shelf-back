from __future__ import annotations

from uuid import UUID

from app.api.exceptions import APIError


class AlbumNotFound(APIError):
    status_code = 404
    code = "ALBUM_NOT_FOUND"
    code_verbose = "Album not found"
    default_message = "The requested album does not exist"


class DownloadNotFound(APIError):
    status_code = 404
    code = "DOWNLOAD_NOT_FOUND"
    code_verbose = "Download not found"
    default_message = "Download has expired or doesn't exist"


class MediaItemContentMetadataNotFound(APIError):
    status_code = 404
    code = "CONTENT_METADATA_NOT_FOUND"
    code_verbose = "No metadata"
    default_message = (
        "Media item '{media_item_id}' doesn't have any associated metadata"
    )

    def __init__(
        self,
        message: str | None = None,
        media_item_id: UUID | str | None = None,
    ):
        super().__init__(message)
        assert media_item_id is not None, (
            "Missing required argument: 'media_item_id'"
        )
        self.message = self.message.format(media_item_id=media_item_id)


class MediaItemNotFound(APIError):
    status_code = 404
    code = "MEDIA_ITEM_NOT_FOUND"
    code_verbose = "Media item not found"
    default_message = "The requested media item does not exist"


class ThumbnailUnavailable(APIError):
    status_code = 400
    code = "THUMBNAIL_UNAVAILABLE"
    code_verbose = "Thumbnail unavailable"
    default_message = "Can't generate thumbnail for the requested media item"
