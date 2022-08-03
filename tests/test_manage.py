from __future__ import annotations

from typing import TYPE_CHECKING, Iterator
from unittest import mock

import edgedb
import pytest
from typer.testing import CliRunner

from app import config
from app.entities import Namespace
from manage import cli

if TYPE_CHECKING:
    from edgedb import Client as DBClient

runner = CliRunner()

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


@pytest.fixture(autouse=True)
async def force_async_setup_teardown_fixtures(db_client):
    """
    A hack fixture to force teardown after sync test run. Actually it is need only if
    you want to run one of the tests from this module.
    """


@pytest.fixture
def db() -> Iterator[DBClient]:
    """Blocking connection to the database."""
    with edgedb.create_client(
        config.DATABASE_DSN,
        max_concurrency=1,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
        tls_security=config.DATABASE_TLS_SECURITY,
    ) as client:
        yield client


def test_createsuperuser(db: DBClient):
    params = ["johndoe", "password", "password"]
    result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
    assert result.exit_code == 0
    assert "User created successfully." in result.stdout

    user = db.query_required_single(
        "SELECT User { username, superuser } FILTER .username = 'johndoe'"
    )
    assert user.username == "johndoe"
    assert user.superuser is True


def test_createsuperuser_but_user_already_exists() -> None:
    params = ["john", "password", "password"]
    result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
    assert result.exit_code == 0

    result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
    assert result.exit_code == 1
    assert str(result.exception) == "Username 'john' is taken"


def test_createsuperuser_ignore_when_user_already_exists() -> None:
    params = ["john", "password", "password"]
    result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
    assert result.exit_code == 0

    result = runner.invoke(cli, "createsuperuser --exist-ok", input="\n".join(params))
    assert result.exit_code == 0
    assert "User already exists, skipping..." in result.stdout


def test_createsuperuser_but_passwords_dont_match() -> None:
    params = ["johndoe", "pass_a", "pass_b", "pass_a", "pass_a"]
    result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
    assert result.exit_code == 0
    assert "Error: The two entered values do not match" in result.stdout


def test_reindex(namespace: Namespace):
    with mock.patch("app.actions.reindex") as reindex_mock:
        result = runner.invoke(cli, ["reindex", str(namespace.path)])

    assert result.exit_code == 0
    assert reindex_mock.call_count == 1
    assert len(reindex_mock.call_args[0]) == 2
    assert isinstance(reindex_mock.call_args[0][0], edgedb.AsyncIOClient)
    assert reindex_mock.call_args[0][1] == namespace


def test_reindex_content(namespace: Namespace):
    with mock.patch("app.actions.reindex_files_content") as reindex_mock:
        result = runner.invoke(cli, ["reindex-content", str(namespace.path)])

    assert result.exit_code == 0
    assert reindex_mock.call_count == 1
    assert len(reindex_mock.call_args[0]) == 2
    assert isinstance(reindex_mock.call_args[0][0], edgedb.AsyncIOClient)
    assert reindex_mock.call_args[0][1] == namespace
