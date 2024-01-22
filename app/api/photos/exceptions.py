from __future__ import annotations

from app.api.exceptions import APIError


class MediaItemNotFound(APIError):
    status_code = 404
    code = "MEDIA_ITEM_NOT_FOUND"
    code_verbose = "Media item not found"
    default_message = "The requested media item does not exist"
