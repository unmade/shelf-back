from __future__ import annotations

import mimetypes
from typing import IO, TYPE_CHECKING, Optional, Union, cast

import filetype

if TYPE_CHECKING:
    from app.typedefs import StrOrPath

FOLDER = "application/directory"
OCTET_STREAM = "application/octet-stream"

mimetypes.init()

mimetypes.add_type("application/sql", ".sql")
mimetypes.add_type("application/x-zsh", ".zsh")
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


def guess(name: StrOrPath, file: Optional[Union[bytes, IO[bytes]]] = None) -> str:
    """
    Guess file media type.

    If optional ``file`` argument is provided, then try to guess media type by checking
    the magic number signature, otherwise fallback to the filename extension.

    Args:
        name (StrOrPath): Filename or path.
        file (Optional[Union[bytes, IO[bytes]]], optional): File-obj. Defaults to None.

    Returns:
        str: Guessed media type. For unknown files returns 'application/octet-stream'.
    """
    if mime := filetype.guess_mime(file):
        return cast(str, mime)

    if mime := mimetypes.guess_type(name, strict=False):
        if isinstance(mime, str):
            return mime
        if mime[0] is not None:
            return mime[0]

    return OCTET_STREAM


def is_image(mediatype: str) -> bool:
    """True if mediatype corresponds to an image file, otherwise False."""
    return mediatype in ("image/jpeg", "image/png", "image/x-icon", "image/webp")
