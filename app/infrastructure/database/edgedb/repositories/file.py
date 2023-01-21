from __future__ import annotations

from typing import TYPE_CHECKING, Iterable
from uuid import UUID

from app import crud
from app.app.repositories import IFileRepository
from app.domain.entities import File

if TYPE_CHECKING:
    from app.entities import File as LegacyFile
    from app.typedefs import StrOrPath


def _from_db(ns_path: str, obj: LegacyFile) -> File:
    return File(
        id=UUID(obj.id),
        ns_path=ns_path,
        name=obj.name,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype,
    )


class FileRepository(IFileRepository):
    def __init__(self, db_context):
        self.db_context = db_context

    @property
    def conn(self):
        return self.db_context.get()

    async def get_by_path_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath],
    ) -> list[File]:
        files = await crud.file.get_many(self.conn,namespace=ns_path, paths=paths)
        return [_from_db(str(ns_path), file) for file in files]
