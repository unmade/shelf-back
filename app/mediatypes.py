from __future__ import annotations

import mimetypes
from typing import IO, TYPE_CHECKING, Optional, Union, cast

import filetype

if TYPE_CHECKING:
    from app.typedefs import StrOrPath

FOLDER = "application/directory"
OCTET_STREAM = "application/octet-stream"

mimetypes.init()
mimetypes.add_type("text/markdown", ".md")


def guess(name: StrOrPath, file: Optional[Union[bytes, IO[bytes]]] = None) -> str:
    """
    Guess file media type.

    If optional ``file`` argument is provided, then try to guess media type checking
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
