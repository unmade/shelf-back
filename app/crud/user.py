from __future__ import annotations

import time
from typing import TYPE_CHECKING

import edgedb

from app import errors, security
from app.entities import User

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection


async def create(conn: AsyncIOConnection, username: str, password: str) -> None:
    """
    Create user, namespace and home folder.

    Args:
        conn (AsyncIOConnection): Connecion to a database.
        username (str): Username for a new user.
        password (str): Plain-text password.

    Raises:
        UserAlreadyExists: If user with a target username already exists.
    """
    query = """
        INSERT File {
            name := <str>$username,
            path := '.',
            size := 0,
            mtime := <float64>$mtime,
            is_dir := True,
            namespace := (
                INSERT Namespace {
                    path := <str>$username,
                    owner := (
                        INSERT User {
                            username := <str>$username,
                            password := <str>$password,
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
            mtime=time.time(),
        )
    except edgedb.ConstraintViolationError as exc:
        raise errors.UserAlreadyExists(f"Username '{username}' is taken") from exc


async def exists(conn: AsyncIOConnection, user_id: str) -> bool:
    """True if User with a given user_id exists, otherwise False."""
    query = """
        SELECT EXISTS (
            SELECT User
            FILTER
                .id = <uuid>$user_id
        )
    """

    return await conn.query_one(query, user_id=str(user_id))


async def get_by_id(conn: AsyncIOConnection, user_id: str) -> User:
    """
    Returns a User with a Namespace.

    Args:
        conn (AsyncIOConnection): Database connection.
        user_id (str): User ID to search for.

    Raises:
        UserNotFound: If User with a target user_id does not exists.

    Returns:
        Account:
    """
    query = """
        SELECT User {
            id,
            username,
            namespace := (
              SELECT User.<owner[IS Namespace] { id, path }
              LIMIT 1
            ),
        }
        FILTER
            .id = <uuid>$user_id
    """
    try:
        return User.from_orm(await conn.query_one(query, user_id=user_id))
    except edgedb.NoDataError as exc:
        raise errors.UserNotFound() from exc


async def get_by_username(conn: AsyncIOConnection, username: str) -> User:
    """
    Returns a User with a target username.

    Args:
        conn (AsyncIOConnection): Database connection.
        username (str): Username to search for.

    Raises:
        UserNotFound: If User with a target username does not exists.

    Returns:
        User: User with a target username.
    """
    query = """
        SELECT User { id, username, password }
        FILTER
            .username = <str>$username
    """

    try:
        return User.from_orm(await conn.query_one(query, username=username))
    except edgedb.NoDataError as exc:
        raise errors.UserNotFound() from exc
