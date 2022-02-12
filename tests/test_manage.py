from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb
import pytest
from typer.testing import CliRunner

from app import config
from manage import cli

if TYPE_CHECKING:
    from edgedb import Client as DBClient

runner = CliRunner()

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


@pytest.fixture
def db_client():
    """Blocking connection to the database."""
    with edgedb.create_client(
        config.DATABASE_DSN,
        max_concurrency=1,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
    ) as client:
        yield client


def test_createsuperuser(db_client: DBClient):
    params = ["johndoe", "password", "password"]
    result = runner.invoke(cli, ["createsuperuser"], input="\n".join(params))
    assert result.exit_code == 0
    assert "User created successfully." in result.stdout

    user = db_client.query_required_single(
        "SELECT User { username, superuser } FILTER .username = 'johndoe'"
    )
    assert user.username == "johndoe"
    assert user.superuser is True


def test_createuser_but_passwords_dont_match():
    params = ["johndoe", "pass_a", "pass_b", "pass_a", "pass_a"]
    result = runner.invoke(cli, ["createsuperuser"], input="\n".join(params))
    assert result.exit_code == 0
    assert "Error: The two entered values do not match" in result.stdout
