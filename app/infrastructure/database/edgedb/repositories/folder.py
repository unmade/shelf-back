from __future__ import annotations

from typing import TYPE_CHECKING, Iterable
from uuid import UUID

from app import crud, mediatypes
from app.app.repositories import IFolderRepository
from app.domain.entities import Folder

if TYPE_CHECKING:
    from app.entities import File
    from app.typedefs import StrOrPath

__all__ = "FolderRepository"


def _from_db(ns_path: str, obj: File) -> Folder:
    return Folder.construct(
        id=UUID(obj.id),
        ns_path=ns_path,
        name=obj.name,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype,
    )


class FolderRepository(IFolderRepository):
    def __init__(self, db_context):
        self.db_context = db_context

    @property
    def conn(self):
        return self.db_context.get()

    async def get_by_path(self, ns_path: StrOrPath, path: StrOrPath) -> Folder:
        obj = await crud.file.get(self.conn, ns_path, path)
        assert obj.mediatype == mediatypes.FOLDER
        return _from_db(str(ns_path), obj)

    async def get_by_path_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath],
    ) -> list[Folder]:
        files = await crud.file.get_many(
            self.conn,
            namespace=ns_path,
            paths=paths,
        )
        assert all(file.mediatype == mediatypes.FOLDER for file in files)
        return [_from_db(str(ns_path), file) for file in files]

    async def save(self, folder: Folder) -> Folder:
        created_folder = await crud.file.create(
            self.conn,
            namespace=folder.ns_path,
            path=folder.path,
            size=folder.size,
            mtime=folder.mtime,
            mediatype=folder.mediatype,
        )
        return folder.copy(update={"id": created_folder.id})
