from __future__ import annotations

import enum

__all__ = ["MediaType"]


class MediaType(str, enum.Enum):
    # application
    FOLDER = "application/directory"
    OCTET_STREAM = "application/octet-stream"

    # image
    IMAGE_BMP = "image/bmp"
    IMAGE_GIF = "image/gif"
    IMAGE_HEIC = "image/heic"
    IMAGE_HEIF = "image/heif"
    IMAGE_ICON = "image/x-icon"
    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_SVG = "image/svg+xml"
    IMAGE_TIFF = "image/tiff"
    IMAGE_WEBP = "image/webp"

    # plain
    PLAIN_TEXT = "plain/text"
