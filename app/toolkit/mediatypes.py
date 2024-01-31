from __future__ import annotations

import enum

__all__ = ["MediaType"]


class MediaType(str, enum.Enum):
    # application
    FOLDER = "application/directory"
    OCTET_STREAM = "application/octet-stream"

    # image
    IMAGE_GIF = "image/gif"
    IMAGE_HEIC = "image/heic"
    IMAGE_HEIF = "image/heif"
    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_WEBP = "image/webp"
    IMAGE_ICON = "image/x-icon"

    # plain
    PLAIN_TEXT = "plain/text"
