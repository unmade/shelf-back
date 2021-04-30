from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

import edgedb

from app import errors
from app.entities import Account

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrUUID


async def count(conn: DBAnyConn) -> int:
    """
    Return the total number of accounts.

    Args:
        conn (DBAnyConn): Database connection.

    Returns:
        int: Total number of Accounts
    """
    return cast(int, await conn.query_one("SELECT count(Account)"))


async def create(
    conn: DBAnyConn,
    username: str,
    *,
    email: Optional[str] = None,
    first_name: str = "",
    last_name: str = ""
) -> Account:
    """
    Create new account for a user.

    Args:
        conn (DBAnyConn): Database connection.
        username (str): Username to create account for.
        email (Optional[str], optional): Email. Defaults to None.
        first_name (str, optional): First name. Defaults to "".
        last_name (str, optional): Last name. Defaults to "".

    Raises:
        errors.UserAlreadyExists: If email is already taken.

    Returns:
        Account: Created account.
    """
    query = """
        SELECT (
            INSERT Account {
                email := <OPTIONAL str>$email,
                first_name := <str>$first_name,
                last_name := <str>$last_name,
                user := (
                    SELECT
                        User
                    FILTER
                        .username = <str>$username
                    LIMIT 1
                )
            }
        ) { id, email, first_name, last_name, user: { username, superuser } }
    """
    try:
        account = await conn.query_one(
            query,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
    except edgedb.ConstraintViolationError as exc:
        raise errors.UserAlreadyExists(f"Email '{email}' is taken") from exc

    return Account.from_db(account)


async def get(conn: DBAnyConn, user_id: StrOrUUID) -> Account:
    """
    Return account for a given user_id.

    Args:
        conn (DBAnyConn): Database connection.
        user_id (StrOrUUID): User id to return account for.

    Raises:
        errors.UserNotFound: If account for given user_id does not exists.

    Returns:
        Account: User Account.
    """
    query = """
        SELECT Account {
            id, email, first_name, last_name, user: { username, superuser }
        }
        FILTER
            .user.id = <uuid>$user_id
        LIMIT 1
    """
    try:
        account = await conn.query_one(query, user_id=user_id)
    except edgedb.NoDataError as exc:
        raise errors.UserNotFound(f"No account for user with id: {user_id}") from exc

    return Account.from_db(account)


async def list_all(conn: DBAnyConn, *, offset: int, limit: int = 25) -> list[Account]:
    """
    List all accounts in the system.

    Args:
        conn (DBAnyConn): Database connection.
        offset (int): Skip this number of elements.
        limit (int, optional): Include only the first element-count elements.

    Returns:
        list[Account]: list of Account
    """
    accounts = await conn.query("""
        SELECT Account {
            id, email, first_name, last_name, user: { username, superuser }
         }
         ORDER BY
            .user.username ASC
         OFFSET <int64>$offset
         LIMIT <int64>$limit
    """, offset=offset, limit=limit)
    return [Account.from_db(account) for account in accounts]
