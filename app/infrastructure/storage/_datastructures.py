from __future__ import annotations

import datetime
from collections.abc import Iterable
from io import IOBase
from typing import NamedTuple

from stream_zip import NO_COMPRESSION_32, NO_COMPRESSION_64, ZIP_32, ZIP_64


class StreamZipFile(NamedTuple):
    path: str
    modified_at: datetime.datetime
    perms: int
    compression: NO_COMPRESSION_32 | NO_COMPRESSION_64 | ZIP_32 | ZIP_64
    content: IOBase | Iterable[bytes]
