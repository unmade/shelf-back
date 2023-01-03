from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import edgedb

from app import errors
from app.entities import Namespace, SharedLink, User

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrPath


def from_db(obj: edgedb.Object) -> SharedLink:
    file = obj.file
    namespace = obj.file.namespace

    return SharedLink.construct(
        id=obj.id,
        token=obj.token,
        file=SharedLink.File.construct(
            id=str(file.id),
            name=file.name,
            path=file.path,
            size=file.size,
            mtime=file.mtime,
            mediatype=file.mediatype.name,
            namespace=Namespace.construct(
                id=namespace.id,
                path=namespace.path,
                owner=User.construct(
                    id=namespace.owner.id,
                    username=namespace.owner.username,
                    superuser=namespace.owner.superuser,
                ),
            )
        )
    )


async def get_or_create(
    conn: DBAnyConn,
    namespace: StrOrPath,
    path: StrOrPath,
) -> SharedLink:
    """
    Get or create shared link for a given file.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Target namespace path.
        path (StrOrPath): Target file path.

    Raises:
        errors.FileNotFound: If file in a given path does not exists.

    Returns:
        SharedLink: Shared link.
    """
    query = """
        WITH
            file := (
                SELECT
                    File
                FILTER
                    str_lower(.path) = str_lower(<str>$path)
                    AND
                    .namespace.path = <str>$namespace
                LIMIT 1
            )
        SELECT (
            INSERT SharedLink {
                token := <str>$token,
                file := file
            }
            UNLESS CONFLICT ON .file
            ELSE (
                SELECT
                    SharedLink
                FILTER
                    .file = file
                LIMIT 1
            )
        ) {
            token,
            file: {
                id,
                name,
                path,
                size,
                mtime,
                mediatype: {
                    name
                },
                namespace: {
                    id,
                    path,
                    owner: {
                        id,
                        username,
                        superuser,
                    }
                }
            }
        }
    """

    token = secrets.token_urlsafe(16)

    try:
        link = await conn.query_required_single(
            query,
            token=token,
            namespace=str(namespace),
            path=str(path),
        )
    except edgedb.MissingRequiredError as exc:
        raise errors.FileNotFound() from exc

    return from_db(link)


async def get(conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath) -> SharedLink:
    """
    Get shared link by a namespace path and file path.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Target namespace path.
        path (StrOrPath): Target file path.

    Raises:
        errors.SharedLinkNotFound: If there is not matching shared link.

    Returns:
        SharedLink: Shared link.
    """
    query = """
        SELECT SharedLink {
            token,
            file: {
                id,
                name,
                path,
                size,
                mtime,
                mediatype: {
                    name
                },
                namespace: {
                    id,
                    path,
                    owner: {
                        id,
                        username,
                        superuser,
                    }
                }
            }
        }
        FILTER
            str_lower(.file.path) = str_lower(<str>$path)
            AND
            .file.namespace.path = <str>$namespace
        LIMIT 1
    """

    ns_path = str(namespace)
    try:
        link = await conn.query_required_single(query, namespace=ns_path, path=path)
    except edgedb.NoDataError as exc:
        raise errors.SharedLinkNotFound() from exc

    return from_db(link)


async def get_by_token(conn: DBAnyConn, token: str) -> SharedLink:
    """
    Get shared link by link token.

    Args:
        conn (DBAnyConn): Database connection.
        token (str): Shared link token.

    Raises:
        errors.SharedLinkNotFound: If there is not matching shared link.

    Returns:
        SharedLink: Shared link.
    """
    query = """
        SELECT SharedLink {
            token,
            file: {
                id,
                name,
                path,
                size,
                mtime,
                mediatype: {
                    name
                },
                namespace: {
                    id,
                    path,
                    owner: {
                        id,
                        username,
                        superuser,
                    }
                }
            }
        }
        FILTER
            .token = <str>$token
        LIMIT 1
    """

    try:
        link = await conn.query_required_single(query, token=token)
    except edgedb.NoDataError as exc:
        raise errors.SharedLinkNotFound() from exc

    return from_db(link)


async def delete(conn: DBAnyConn, token: str) -> None:
    """
    Delete shared link.

    Args:
        conn (DBAnyConn): Database connection.
        token (str): Token to be revoked.
    """
    query = """
        DELETE
            SharedLink
        FILTER
            .token = <str>$token
    """

    await conn.query_single(query, token=token)
