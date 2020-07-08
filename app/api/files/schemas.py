from __future__ import annotations

from pydantic import BaseModel


class FolderPath(BaseModel):
    path: str
