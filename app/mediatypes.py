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


def guess(
    name: StrOrPath,
    content: IO[bytes] | None = None,
    unsafe: bool = False,
) -> str:
    """
    Guess file media type.

    If optional ``content`` argument is provided, then try to guess media type by
    checking the magic number signature, otherwise fallback to the filename extension.

    Args:
        name (StrOrPath): Filename or path.
        content (IO[bytes | None, optional): File-obj. Defaults to None.
        unsafe (bool, optional): Whether to allow fallback to filename extension for
            types that can be identified by magic number signature. Defaults to False.

    Returns:
        str: Guessed media type. For unknown files returns 'application/octet-stream'.
    """
    if content is not None:
        content.seek(0)

    if mime := filetype.guess_mime(content):
        return cast(str, mime)

    mime, _ = mimetypes.guess_type(name, strict=False)
    if not unsafe and mime in _STRICT_MEDIATYPES:
        return OCTET_STREAM

    if mime is None:
        return OCTET_STREAM

    return cast(str, mime)
