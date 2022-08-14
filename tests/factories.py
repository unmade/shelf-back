from __future__ import annotations

import os.path
import time
from io import BytesIO
from typing import TYPE_CHECKING

from faker import Faker

from app import config, crud, mediatypes, security, timezone
from app.entities import Account, Exif, File, FileMetadata, Fingerprint, Namespace, User
from app.storage import storage

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrPath, StrOrUUID

fake = Faker()


class AccountFactory:
    __slots__ = ["_db_conn"]

    def __init__(self, db_conn: DBAnyConn) -> None:
        self._db_conn = db_conn

    async def __call__(
        self,
        email: str | None = None,
        first_name: str = "",
        last_name: str = "",
        storage_quota: int | None = None,
        user: User | None = None,
    ) -> Account:
        if user is None:
            user = await UserFactory(self._db_conn)()

        query = """
            SELECT (
                INSERT Account {
                    email := <OPTIONAL str>$email,
                    first_name := <str>$first_name,
                    last_name := <str>$last_name,
                    storage_quota := <OPTIONAL int64>$storage_quota,
                    created_at := <datetime>$created_at,
                    user := (
                        SELECT
                            User
                        FILTER
                            .id = <uuid>$user_id
                    ),
                }
            ) { id, email, first_name, last_name, user: { username, superuser } }
        """

        return crud.account.from_db(
            await self._db_conn.query_required_single(
                query,
                email=email,
                user_id=user.id,
                first_name=first_name,
                last_name=last_name,
                storage_quota=storage_quota,
                created_at=timezone.now(),
            )
        )


class BookmarkFactory:
    __slots__ = ["_db_conn"]

    def __init__(self, db_conn: DBAnyConn) -> None:
        self._db_conn = db_conn

    async def __call__(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        query = """
            UPDATE
                User
            FILTER
                .id = <uuid>$user_id
            SET {
                bookmarks += (
                    SELECT
                        File
                    FILTER
                        .id = <uuid>$file_id
                )
            }
        """

        await self._db_conn.query_required_single(
            query, user_id=user_id, file_id=file_id
        )


class FileFactory:
    __slots__ = ["_db_conn"]

    def __init__(self, db_conn: DBAnyConn) -> None:
        self._db_conn = db_conn

    async def __call__(
        self,
        ns_path: StrOrPath,
        path: StrOrPath = None,
        content: bytes | BytesIO = b"I'm Dummy File!",
    ) -> File:
        path = path or fake.unique.file_name(category="text", extension="txt")
        parent = os.path.normpath(os.path.dirname(path))

        await storage.makedirs(ns_path, parent)
        if not await crud.file.exists(self._db_conn, ns_path, parent):
            await crud.file.create_folder(self._db_conn, ns_path, parent)

        if isinstance(content, bytes):
            content = BytesIO(content)

        file = await storage.save(ns_path, path, content=content)
        return await crud.file.create(
            self._db_conn,
            ns_path,
            path,
            size=file.size,
            mediatype=mediatypes.guess(path, content)
        )


class FileMetadataFactory:
    __slots__ = ["_db_conn"]

    def __init__(self, db_conn: DBAnyConn) -> None:
        self._db_conn = db_conn

    async def __call__(
        self,
        file_id: StrOrUUID,
        data: Exif,
    ) -> FileMetadata:
        return crud.metadata.from_db(
            await self._db_conn.query_required_single("""
                SELECT (
                    INSERT FileMetadata {
                        data := <json>$data,
                        file := (
                            SELECT
                                File
                            FILTER
                                .id = <uuid>$file_id
                            LIMIT 1
                        ),
                    }
                ) { data, file: { id } }
            """, file_id=file_id, data=data.json())
        )


class FingerprintFactory:
    __slots__ = ["_db_conn"]

    def __init__(self, db_conn: DBAnyConn) -> None:
        self._db_conn = db_conn

    async def __call__(
        self,
        file_id: StrOrUUID,
        part1: int,
        part2: int,
        part3: int,
        part4: int,
    ) -> Fingerprint:
        return crud.fingerprint.from_db(
            await self._db_conn.query_required_single("""
                SELECT (
                    INSERT Fingerprint {
                        part1 := <int32>$part1,
                        part2 := <int32>$part2,
                        part3 := <int32>$part3,
                        part4 := <int32>$part4,
                        file := (
                            SELECT
                                File
                            FILTER
                                .id = <uuid>$file_id
                        )
                    }
                ) { part1, part2, part3, part4, file: { id } }
            """, file_id=file_id, part1=part1, part2=part2, part3=part3, part4=part4)
        )


class MediaTypeFactory:
    __slots__ = ["_db_conn"]

    def __init__(self, db_conn: DBAnyConn) -> None:
        self._db_conn = db_conn

    async def __call__(self, name: str) -> str:
        await self._db_conn.query("""
            INSERT MediaType {
                name := <str>$name
            }
            UNLESS CONFLICT
        """, name=name)
        return name


class NamespaceFactory:
    __slots__ = ["_db_conn"]

    def __init__(self, db_conn: DBAnyConn) -> None:
        self._db_conn = db_conn

    async def __call__(self) -> Namespace:
        owner = await UserFactory(self._db_conn)()
        namespace = crud.namespace.from_db(
            await self._db_conn.query_required_single("""
                SELECT (
                    INSERT Namespace {
                        path := <str>$path,
                        owner := (
                            SELECT
                                User
                            FILTER
                                .id = <uuid>$owner_id
                        )
                    }
                ) { id, path, owner: { id, username, superuser } }
            """, path=owner.username, owner_id=owner.id)
        )

        query = """
            INSERT File {
                name := <str>$name,
                path := <str>$path,
                size := 0,
                mtime := <float64>$mtime,
                mediatype := (
                    INSERT MediaType {
                        name := <str>$mediatype
                    }
                    UNLESS CONFLICT ON .name
                    ELSE (
                        SELECT
                            MediaType
                        FILTER
                            .name = <str>$mediatype
                    )
                ),
                namespace := (
                    SELECT
                        Namespace
                    FILTER
                        .id = <uuid>$namespace_id
                    LIMIT 1
                )
            }
        """

        await self._db_conn.query_required_single(
            query,
            name=str(namespace.path),
            path=".",
            mtime=time.time(),
            mediatype=mediatypes.FOLDER,
            namespace_id=namespace.id,
        )

        await self._db_conn.query_required_single(
            query,
            name=config.TRASH_FOLDER_NAME,
            path=config.TRASH_FOLDER_NAME,
            mtime=time.time(),
            mediatype=mediatypes.FOLDER,
            namespace_id=namespace.id,
        )

        await storage.makedirs(namespace.path, ".")
        await storage.makedirs(namespace.path, config.TRASH_FOLDER_NAME)

        return namespace


class UserFactory:
    __slots__ = ["_db_conn"]

    def __init__(self, db_conn: DBAnyConn) -> None:
        self._db_conn = db_conn

    async def __call__(
        self,
        username: str = None,
        password: str = "root",
        superuser: bool = False,
        hash_password: bool = False,
    ) -> User:
        username = username or fake.unique.user_name()
        if hash_password:
            password = security.make_password(password)

        # create user with plain query, cause crud.user.create do too much stuff
        return crud.user.from_db(
            await self._db_conn.query_required_single("""
                SELECT (
                    INSERT User {
                        username := <str>$username,
                        password := <str>$password,
                        superuser := <bool>$superuser,
                    }
                ) { id, username, superuser }
            """, username=username, password=password, superuser=superuser)
        )
