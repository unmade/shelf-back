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


@pytest.fixture(scope="module", autouse=True)
def setUp():
    with (
        mock.patch("manage._create_database"),
        mock.patch("manage._create_storage"),
    ):
        yield


class TestCreateSuperuser:
    @pytest.fixture
    def create_superuser(self):
        target = "app.app.users.usecases.UserUseCase.create_superuser"
        with mock.patch(target) as patch:
            yield patch

    def test(self, create_superuser: MagicMock):
        # GIVEN
        params = ["johndoe", "password", "password"]
        # WHEN
        result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
        # THEN
        assert result.exit_code == 0
        assert "User created successfully." in result.stdout
        create_superuser.assert_awaited_once_with("johndoe", "password")

    def test_when_user_already_exists(self, create_superuser: MagicMock):
        # GIVEN
        create_superuser.side_effect = User.AlreadyExists("Username is taken")
        params = ["john", "password", "password"]
        # WHEN
        result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
        # THEN
        assert result.exit_code == 1
        assert str(result.exception) == "Username is taken"
        create_superuser.assert_awaited_once_with("john", "password")

    def test_exists_ok_flag(self, create_superuser: MagicMock):
        # GIVEN
        create_superuser.side_effect = User.AlreadyExists("Username is taken")
        input_ = "\n".join(["john", "password", "password"])
        # WHEN
        result = runner.invoke(cli, "createsuperuser --exist-ok", input=input_)
        # THEN
        assert result.exit_code == 0
        assert "User already exists, skipping..." in result.stdout
        create_superuser.assert_awaited_once_with("john", "password")

    def test_when_passwords_dont_match(self, create_superuser: MagicMock):
        # GIVEN
        params = ["johndoe", "pass_a", "pass_b", "pass_a", "pass_a"]
        # WHEN
        result = runner.invoke(cli, "createsuperuser", input="\n".join(params))
        # THEN
        assert result.exit_code == 0
        assert "Error: The two entered values do not match" in result.stdout
        assert create_superuser.await_count == 1


class TestReindex:
    def test(self):
        target = "app.app.files.usecases.NamespaceUseCase.reindex"
        with mock.patch(target) as reindex_mock:
            result = runner.invoke(cli, ["reindex", "admin"])

        assert result.exit_code == 0
        reindex_mock.assert_awaited_once_with("admin")


class TestReindexContent:
    def test_reindex_content(self):
        target = "app.app.files.usecases.NamespaceUseCase.reindex_contents"
        with mock.patch(target) as reindex_mock:
            result = runner.invoke(cli, ["reindex-content", "admin"])

        assert result.exit_code == 0
        reindex_mock.assert_awaited_once_with("admin")
