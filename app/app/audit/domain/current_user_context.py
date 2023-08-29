from __future__ import annotations

from contextvars import ContextVar, Token
from typing import ClassVar, Self
from uuid import UUID

from pydantic import BaseModel, PrivateAttr

__all__ = [
    "CurrentUser",
    "CurrentUserContext",
    "current_user_ctx",
]

current_user_ctx: ContextVar[CurrentUserContext] = ContextVar("current_user_ctx")


class CurrentUser(BaseModel):
    id: UUID
    username: str


class CurrentUserContext(BaseModel):
    User: ClassVar[type[CurrentUser]] = CurrentUser

    user: CurrentUser
    _token: Token[CurrentUserContext] | None = PrivateAttr(None)

    def __enter__(self) -> Self:
        self._token = current_user_ctx.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        assert self._token is not None
        current_user_ctx.reset(self._token)

    def __reduce__(self):
        return (self.model_validate, ({"user": self.user}, ))
