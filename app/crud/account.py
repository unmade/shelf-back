from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, cast, get_type_hints

import edgedb

from app import db, errors
from app.entities import Account

from . import user

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrUUID


class AccountUpdate(TypedDict, total=False):
    email: str | None
    first_name: str
    last_name: str


def from_db(obj: edgedb.Object) -> Account:
    return Account.construct(
        id=obj.id,
        email=obj.email,
        first_name=obj.first_name,
        last_name=obj.last_name,
        user=user.from_db(obj.user),
    )


async def count(conn: DBAnyConn) -> int:
    """
    Return the total number of accounts.

    Args:
        conn (DBAnyConn): Database connection.

    Returns:
        int: Total number of Accounts
    """
    return cast(int, await conn.query_single("SELECT count(Account)"))


async def create(
    conn: DBAnyConn,
    username: str,
    *,
    email: str | None = None,
    first_name: str = "",
    last_name: str = ""
) -> Account:
    """
    Create new account for a user.

    Args:
        conn (DBAnyConn): Database connection.
        username (str): Username to create account for.
        email (str | None, optional): Email. Defaults to None.
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
        ) { id, email, first_name, last_name, user: { id, username, superuser } }
    """
    try:
        account = await conn.query_single(
            query,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
    except edgedb.ConstraintViolationError as exc:
        raise errors.UserAlreadyExists(f"Email '{email}' is taken") from exc

    return from_db(account)


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
        account = await conn.query_single(query, user_id=user_id)
    except edgedb.NoDataError as exc:
        raise errors.UserNotFound(f"No account for user with id: {user_id}") from exc

    return from_db(account)


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
    return [from_db(account) for account in accounts]


async def update(conn: DBAnyConn, user_id, fields: AccountUpdate) -> Account:
    hints = get_type_hints(AccountUpdate)
    statements = [f"{key} := {db.autocast(hints[key])}${key}" for key in fields]
    query = f"""
        SELECT (
            UPDATE Account
            FILTER
                .user.id = <uuid>$user_id
            SET {{
                {','.join(statements)}
            }}
        ) {{ id, email, first_name, last_name, user: {{  username, superuser }} }}
    """
    account = await conn.query_single(query, user_id=user_id, **fields)
    return from_db(account)
