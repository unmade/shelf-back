from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import edgedb
import pytest
from typer.testing import CliRunner

from app import errors
from manage import cli

if TYPE_CHECKING:
    from unittest.mock import MagicMock

runner = CliRunner()


@pytest.fixture(autouse=True)
def setUp():
    with (
        mock.patch("manage._create_database"),
        mock.patch("manage._create_storage"),
    ):
        yield


class TestCreateSuperuser:
    @pytest.fixture
    def create_namespace(self):
        target = "app.app.services.NamespaceService.create"
        with mock.patch(target) as patch:
            yield patch

    @pytest.fixture
    def create_user(self):
        target = "app.app.services.UserService.create"
        with mock.patch(target) as patch:
            yield patch

    def test(self, create_namespace: MagicMock, create_user: MagicMock):
        params = ["johndoe", "password", "password"]
        result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
        assert result.exit_code == 0
        assert "User created successfully." in result.stdout

        create_user.assert_awaited_once_with("johndoe", "password", superuser=True)
        user = create_user.return_value
        create_namespace.assert_awaited_once_with(user.username, owner_id=user.id)

    def test_when_user_already_exists(
        self, create_namespace: MagicMock, create_user: MagicMock
    ):
        create_user.side_effect = errors.UserAlreadyExists("Username is taken")
        params = ["john", "password", "password"]
        result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
        assert result.exit_code == 1
        assert str(result.exception) == "Username is taken"
        create_user.assert_awaited_once_with("john", "password", superuser=True)
        create_namespace.assert_not_awaited()

    def test_exists_ok_flag(self, create_namespace: MagicMock, create_user: MagicMock):
        create_user.side_effect = errors.UserAlreadyExists("Username is taken")
        input_ = "\n".join(["john", "password", "password"])
        result = runner.invoke(cli, "createsuperuser --exist-ok", input=input_)
        assert result.exit_code == 0
        assert "User already exists, skipping..." in result.stdout
        create_user.assert_awaited_once_with("john", "password", superuser=True)
        create_namespace.assert_not_awaited()

    def test_when_passwords_dont_match(
        self, create_namespace: MagicMock, create_user: MagicMock
    ):
        params = ["johndoe", "pass_a", "pass_b", "pass_a", "pass_a"]
        result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
        assert result.exit_code == 0
        assert "Error: The two entered values do not match" in result.stdout
        assert create_user.await_count == 1
        assert create_namespace.await_count == 1


class TestReindex:
    def test_reindex(self):
        with (
            mock.patch("app.crud.namespace.get") as get_namespace_mock,
            mock.patch("app.actions.reindex") as reindex_mock,
        ):
            result = runner.invoke(cli, ["reindex", "admin"])

        get_namespace_mock.assert_awaited_once()
        namespace = get_namespace_mock.return_value

        assert result.exit_code == 0
        assert reindex_mock.call_count == 1
        assert len(reindex_mock.call_args[0]) == 2
        assert isinstance(reindex_mock.call_args[0][0], edgedb.AsyncIOClient)
        assert reindex_mock.call_args[0][1] == namespace


class TestReindexContent:
    def test_reindex_content(self):
        with (
            mock.patch("app.crud.namespace.get") as get_namespace_mock,
            mock.patch("app.actions.reindex_files_content") as reindex_mock,
        ):
            result = runner.invoke(cli, ["reindex-content", "admin"])

        get_namespace_mock.assert_awaited_once()
        namespace = get_namespace_mock.return_value

        assert result.exit_code == 0
        assert reindex_mock.call_count == 1
        assert len(reindex_mock.call_args[0]) == 2
        assert isinstance(reindex_mock.call_args[0][0], edgedb.AsyncIOClient)
        assert reindex_mock.call_args[0][1] == namespace
