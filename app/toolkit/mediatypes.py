from __future__ import annotations

import enum
import mimetypes
import re
from typing import IO, TYPE_CHECKING, cast

import filetype

if TYPE_CHECKING:
    from pathlib import PurePath

__all__ = ["MediaType", "guess", "guess_unsafe"]


SVG_PATTERN = r'(?:<\?xml\b[^>]*>[^<]*)?(?:<!--.*?-->[^<]*)*(?:<svg|<!DOCTYPE svg)\b'
SVG_RE = re.compile(SVG_PATTERN, re.DOTALL)

mimetypes.init()

mimetypes.add_type("application/sql", ".sql")
mimetypes.add_type("application/x-zsh", ".zsh")
mimetypes.add_type("image/heif", ".heif")
mimetypes.add_type("image/heif", ".hif")
mimetypes.add_type("text/jsx", ".jsx")
mimetypes.add_type("text/markdown", ".md")
mimetypes.add_type("text/plain", ".cfg")
mimetypes.add_type("text/plain", ".ini")
mimetypes.add_type("text/x-coffeescript", ".coffee")
mimetypes.add_type("text/x-go", ".go")
mimetypes.add_type("text/x-nim", ".nim")
mimetypes.add_type("text/x-yml", ".yaml")
mimetypes.add_type("text/x-yml", ".yml")
mimetypes.add_type("text/x-python", ".pyi")
mimetypes.add_type("text/x-python", ".pyx")
mimetypes.add_type("text/x-swift", ".swift")
mimetypes.add_type("text/x-plist", ".plist")
mimetypes.add_type("text/x-rst", ".rst")
mimetypes.add_type("text/x-rust", ".rs")
mimetypes.add_type("text/x-toml", ".toml")
mimetypes.add_type("text/x-vim", ".vim")

_STRICT_MEDIATYPES = {
    tp.MIME
    for tp in filetype.TYPES
}


class MediaType(enum.StrEnum):
    # application
    EPUB = "application/epub+zip"
    FOLDER = "application/directory"
    OCTET_STREAM = "application/octet-stream"
    PDF = "application/pdf"

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
    TEXT_PLAIN = "text/plain"


def guess(content: IO[bytes], *, name: str | PurePath | None = None) -> str:
    """
    Guesses file media type by checking the content magic number signature or by
    file name extension if media type can't be guessed by content.

    Note, that for file extension that are expected to be guessed by magic numbers the
    function will always return 'application/octet-stream'.

    Returns:
        str: Guessed media type. For unknown files returns 'application/octet-stream'.
    """
    content.seek(0)
    if mime := filetype.guess_mime(content):
        return cast(str, mime)

    content.seek(0)
    if SVG_RE.match(content.read().decode('latin-1')) is not None:
        return MediaType.IMAGE_SVG.value

    if name is not None:
        mime = guess_unsafe(name)
        if mime not in _STRICT_MEDIATYPES:
            return mime

    return MediaType.OCTET_STREAM.value


def guess_unsafe(name: str | PurePath) -> str:
    """
    Guesses file media type by a filename extension.

    Returns:
        str: Guessed media type. For unknown files returns 'application/octet-stream'.
    """
    mime, _ = mimetypes.guess_type(str(name), strict=False)
    if mime is None:
        return MediaType.OCTET_STREAM.value
    return mime
