from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest
from typer.testing import CliRunner

from app.app.users.domain import User
from manage import cli

if TYPE_CHECKING:
    from unittest.mock import MagicMock

pytestmark = [pytest.mark.asyncio]

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
        create_user.side_effect = User.AlreadyExists("Username is taken")
        params = ["john", "password", "password"]
        result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
        assert result.exit_code == 1
        assert str(result.exception) == "Username is taken"
        create_user.assert_awaited_once_with("john", "password", superuser=True)
        create_namespace.assert_not_awaited()

    def test_exists_ok_flag(self, create_namespace: MagicMock, create_user: MagicMock):
        create_user.side_effect = User.AlreadyExists("Username is taken")
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
    def test(self):
        with mock.patch("app.app.managers.NamespaceManager.reindex") as reindex_mock:
            result = runner.invoke(cli, ["reindex", "admin"])

        assert result.exit_code == 0
        reindex_mock.assert_awaited_once_with("admin")


class TestReindexContent:
    def test_reindex_content(self):
        target = "app.app.managers.NamespaceManager.reindex_contents"
        with mock.patch(target) as reindex_mock:
            result = runner.invoke(cli, ["reindex-content", "admin"])

        assert result.exit_code == 0
        reindex_mock.assert_awaited_once_with("admin")
