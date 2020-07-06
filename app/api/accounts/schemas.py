from __future__ import annotations

from pydantic import BaseModel


class UserMe(BaseModel):
    username: str

    class Config:
        orm_mode = True
