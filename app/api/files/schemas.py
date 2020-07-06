from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class FolderPath(BaseModel):
    path: Optional[str]
