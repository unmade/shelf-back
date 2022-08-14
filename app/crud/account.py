from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, cast, get_type_hints

import edgedb

from app import db, errors, timezone
from app.entities import Account

from . import user

if TYPE_CHECKING:
    from datetime import datetime

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
    return cast(int, await conn.query_required_single("SELECT count(Account)"))


async def create(
    conn: DBAnyConn,
    username: str,
    *,
    email: str | None = None,
    first_name: str = "",
    last_name: str = "",
    storage_quota: int | None = None,
    created_at: datetime | None = None,
) -> Account:
    """
    Create new account for a user.

    Args:
        conn (DBAnyConn): Database connection.
        username (str): Username to create account for.
        email (str | None, optional): Email. Defaults to None.
        first_name (str, optional): First name. Defaults to "".
        last_name (str, optional): Last name. Defaults to "".
        storage_quota (int | None, optional): Storage quota. Defaults to None.
        created_at (datetime | None, optional): Timezone-aware datetime of when this
            account is created. If None, then the current datetime is used.

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
                storage_quota := <OPTIONAL int64>$storage_quota,
                created_at := <datetime>$created_at,
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
        account = await conn.query_required_single(
            query,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            storage_quota=storage_quota,
            created_at=created_at or timezone.now(),
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
        account = await conn.query_required_single(query, user_id=user_id)
    except edgedb.NoDataError as exc:
        raise errors.UserNotFound(f"No account for user with id: {user_id}") from exc

    return from_db(account)


async def get_space_usage(conn: DBAnyConn, user_id: StrOrUUID) -> tuple[int, int]:
    query = """
        WITH
            namespaces := (
                SELECT
                    Namespace
                FILTER
                    .owner.id = <uuid>$user_id
            ),
            used := (
                SELECT sum((
                    SELECT
                        File { size }
                    FILTER
                        .namespace IN namespaces
                        AND
                        .path = '.'
                ).size)
            ),
            quota := (
                SELECT
                    Account { storage_quota }
                FILTER
                    .user.id = <uuid>$user_id
                LIMIT 1
            ).storage_quota,
        SELECT {
            used := used,
            quota := quota
        }
    """

    result = await conn.query_required_single(query, user_id=user_id)
    return result.used, result.quota


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
        LIMIT 1
    """
    account = await conn.query_required_single(query, user_id=user_id, **fields)
    return from_db(account)
