from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

StrOrPath = Union[str, Path]
StrOrUUID = Union[str, UUID]
