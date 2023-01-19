from __future__ import annotations

from typing import Protocol

from app.domain.entities import Folder


class IFolderRepository(Protocol):
    async def save(self, folder: Folder) -> Folder:
        """
        Saves a folder to a database.

        Args:
            folder (Folder): a Folder instance to save.

        Raises:
            FileAlreadyExists: If file in a target path already exists.
            MissingParent: If target path does not have a parent.
            NotADirectory: If parent path is not a directory.

        Returns:
            Folder: Created folder.
        """
