from __future__ import annotations

import datetime
from collections.abc import Iterable
from io import IOBase
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from stream_zip import (
        _NO_COMPRESSION_32_TYPE,
        _NO_COMPRESSION_64_TYPE,
        _ZIP_32_TYPE,
        _ZIP_64_TYPE,
    )

    CompressionTypes = (
        _NO_COMPRESSION_32_TYPE
        | _NO_COMPRESSION_64_TYPE
        | _ZIP_32_TYPE
        | _ZIP_64_TYPE
    )


class StreamZipFile(NamedTuple):
    path: str
    modified_at: datetime.datetime
    perms: int
    compression: CompressionTypes
    content: IOBase | Iterable[bytes]
