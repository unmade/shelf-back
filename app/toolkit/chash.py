from __future__ import annotations

import hashlib
from typing import IO

__all__ = [
    "EMPTY_CONTENT_HASH",
    "chash",
]

EMPTY_CONTENT_HASH = ""

_DROPBOX_HASH_CHUNK_SIZE = 4*1024*1024


def chash(content: IO[bytes]) -> str:
    """
    Calculates a Dropbox content hash as described in:
        https://www.dropbox.com/developers/reference/content-hash

    Return empty string for empty content.
    """
    block_hashes = b""
    content.seek(0)
    while True:
        chunk = content.read(_DROPBOX_HASH_CHUNK_SIZE)
        if not chunk:
            break
        block_hashes += hashlib.sha256(chunk).digest()
    content.seek(0)

    if block_hashes == b"":
        return EMPTY_CONTENT_HASH
    return hashlib.sha256(block_hashes).hexdigest()
