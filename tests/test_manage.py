from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb
import pytest
from manage import cli
from typer.testing import CliRunner

from app import config

if TYPE_CHECKING:
    from edgedb import BlockingIOConnection as DBConn

runner = CliRunner()

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
def conn():
    """Blocking connection to the database."""
    conn = edgedb.connect(config.EDGEDB_DSN)
    try:
        yield conn
    finally:
        conn.close()


def test_createsuperuser(conn: DBConn):
    params = ["johndoe", "password", "password"]
    result = runner.invoke(cli, ["createsuperuser"], input="\n".join(params))
    assert result.exit_code == 0
    assert "User created successfully." in result.stdout

    user = conn.query_one(
        "SELECT User { username, superuser } FILTER .username = 'johndoe'"
    )
    assert user.username == "johndoe"
    assert user.superuser is True


def test_createuser_but_passwords_dont_match():
    params = ["johndoe", "pass_a", "pass_b", "pass_a", "pass_a"]
    result = runner.invoke(cli, ["createsuperuser"], input="\n".join(params))
    assert result.exit_code == 0
    assert "Error: the two entered values do not match" in result.stdout