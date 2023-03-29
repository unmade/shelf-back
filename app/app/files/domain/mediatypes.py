from __future__ import annotations

import mimetypes
from typing import IO, TYPE_CHECKING, cast

import filetype

if TYPE_CHECKING:
    from app.typedefs import StrOrPath

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

FOLDER = "application/directory"

IMAGE_GIF = "image/gif"
IMAGE_HEIC = "image/heic"
IMAGE_HEIF = "image/heif"
IMAGE_JPEG = "image/jpeg"
IMAGE_PNG = "image/png"
IMAGE_WEBP = "image/webp"
IMAGE_ICON = "image/x-icon"

OCTET_STREAM = "application/octet-stream"

_STRICT_MEDIATYPES = {
    tp.MIME
    for tp in filetype.TYPES
}


def guess(content: IO[bytes], *, name: StrOrPath | None = None) -> str:
    """
    Guesses file media type by checking the content magic number signature or by
    file name extension if media type can't be guessed by content.

    Note, that for file extension that are expected to be guessed by magic numbers the
    function will always return 'application/octet-stream'.

    Args:
        content (IO[bytes]): File-obj. Defaults to None.
        name ()

    Returns:
        str: Guessed media type. For unknown files returns 'application/octet-stream'.
    """
    content.seek(0)
    if mime := filetype.guess_mime(content):
        return cast(str, mime)

    if name is not None:
        mime = guess_unsafe(name)
        if mime not in _STRICT_MEDIATYPES:
            return cast(str, mime)

    return OCTET_STREAM


def guess_unsafe(name: StrOrPath) -> str:
    """
    Guesses file media type by a filename extension.

    Args:
        name (StrOrPath): Filename or path.

    Returns:
        str: Guessed media type. For unknown files returns 'application/octet-stream'.
    """
    mime, _ = mimetypes.guess_type(name, strict=False)
    if mime is None:
        return OCTET_STREAM
    return mime
