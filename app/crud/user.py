from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

import edgedb

from app import errors, mediatypes, security
from app.entities import User

if TYPE_CHECKING:
    from uuid import UUID
    from app.typedefs import DBAnyConn, StrOrUUID


async def create(
    conn: DBAnyConn, username: str, password: str, *, superuser: bool = False,
) -> None:
    """
    Create user, namespace and home folder.

    Args:
        conn (DBAnyConn): Connection to a database.
        username (str): Username for a new user.
        password (str): Plain-text password.
        superuser (bool, optional): Whether user is superuser or not. Defaults to
            False.

    Raises:
        UserAlreadyExists: If user with a target username already exists.
    """
    query = """
        INSERT File {
            name := <str>$username,
            path := '.',
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
                INSERT Namespace {
                    path := <str>$username,
                    owner := (
                        INSERT User {
                            username := <str>$username,
                            password := <str>$password,
                            superuser := <bool>$superuser,
                        }
                    )
                }
            )
        }
    """

    try:
        await conn.query(
            query,
            username=username,
            password=security.make_password(password),
            superuser=superuser,
            mtime=time.time(),
            mediatype=mediatypes.FOLDER,
        )
    except edgedb.ConstraintViolationError as exc:
        raise errors.UserAlreadyExists(f"Username '{username}' is taken") from exc


async def exists(conn: DBAnyConn, user_id: StrOrUUID) -> bool:
    """True if User with a given user_id exists, otherwise False."""
    query = """
        SELECT EXISTS (
            SELECT
                User
            FILTER
                .id = <uuid>$user_id
        )
    """

    return cast(bool, await conn.query_single(query, user_id=str(user_id)))


async def get_by_id(conn: DBAnyConn, user_id: StrOrUUID) -> User:
    """
    Return a User with a Namespace.

    Args:
        conn (DBAnyConn): Database connection.
        user_id (StrOrUUID): User ID to search for.

    Raises:
        UserNotFound: If User with a target user_id does not exists.

    Returns:
        User:
    """
    query = """
        SELECT
            User {
                id, username, superuser,
            }
        FILTER
            .id = <uuid>$user_id
    """
    try:
        return User.from_orm(await conn.query_single(query, user_id=user_id))
    except edgedb.NoDataError as exc:
        raise errors.UserNotFound(f"No user with id: '{user_id}'") from exc


async def get_password(conn: DBAnyConn, username: str) -> tuple[UUID, str]:
    """
    Returns User password by username.

    Args:
        conn (DBAnyConn): Database connection.
        username (str): Target username to return password for.

    Raises:
        errors.UserNotFound: If user with this username does not exists.

    Returns:
        tuple[UUID, str]: A tuple with User id and password.
    """
    query = """
        SELECT
            User {
                id, password
            }
        FILTER
            .username = <str>$username
    """

    try:
        user = await conn.query_single(query, username=username)
    except edgedb.NoDataError as exc:
        raise errors.UserNotFound(f"No user with username: '{username}'") from exc

    return user.id, user.password
