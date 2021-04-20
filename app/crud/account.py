from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import edgedb

from app import errors
from app.entities import Account

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn


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
        conn (DBAnyConn): Connection to the database.
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
        ) { id, email, first_name, last_name, user: { username } }
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
