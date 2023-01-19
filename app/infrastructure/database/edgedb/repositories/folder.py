from __future__ import annotations

from app import crud
from app.app.repositories import IFolderRepository
from app.domain.entities import Folder


class FolderRepository(IFolderRepository):
    def __init__(self, db_context):
        self.db_context = db_context

    @property
    def conn(self):
        return self.db_context.get()

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
