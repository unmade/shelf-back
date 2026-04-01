from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import AnyHttpUrl

from app.config import (
    _BASE_DIR,
    DatabaseDSN,
    FileSystemStorageConfig,
    S3StorageConfig,
    StoragesConfig,
    StorageType,
    _as_absolute_path,
    _parse_bytes_size,
    _parse_timedelta_from_str,
)


class TestAsAbsolutePath:
    @pytest.mark.parametrize(["given", "expected"], [
        (None, None),
        ("./app", str(_BASE_DIR / "./app")),
        ("app", str(_BASE_DIR / "./app")),
        ("/usr/bin/src", "/usr/bin/src"),
    ])
    def test(self, given: str, expected: str):
        assert _as_absolute_path(given) == expected


class TestParseBytesSize:
    @pytest.mark.parametrize(["given", "expected"], [
        (512, 512),
        ("0B", 0),
        ("1B", 1),
        ("256", 256),
        ("1kb", 1024),
        (" 1KB ", 1024),
        ("1.0KB", 1024),
        ("1.50KB", 1024 + 512),
        ("2MB", 2* 2**20),
        ("4GB", 4 * 2**30),
    ])
    def test(self, given: int | str, expected: str):
        assert _parse_bytes_size(given) == expected

    @pytest.mark.parametrize("given", [
        "",
        "KB",
        "1.5.KB",
        "1.5.0KB",
        "1 KB",
        "-1KB",
    ])
    def test_when_value_is_invalid(self, given: str):
        with pytest.raises(ValueError) as excinfo:
            _parse_bytes_size(given)
        msg = 'string in a valid format required (e.g. "1KB", "1.5GB")'
        assert str(excinfo.value) == msg

    def test_non_string_value(self):
        given = object()
        result = _parse_timedelta_from_str(given)
        assert result is given


class TestParseTimedeltaFromStr:
    @pytest.mark.parametrize(["given", "expected"], [
        ("1s", timedelta(seconds=1)),
        ("2m", timedelta(minutes=2)),
        ("4h", timedelta(hours=4)),
        ("7d", timedelta(days=7)),
        ("2h30s", timedelta(hours=2, seconds=30)),
        (" 1d2H30m15S ", timedelta(days=1, hours=2, minutes=30, seconds=15)),
    ])
    def test(self, given: str | timedelta, expected: str):
        assert _parse_timedelta_from_str(given) == expected

    @pytest.mark.parametrize("given", [
        "",
        "1",
        "s",
        "1.5s",
        "-1s",
        "1 d",
        "2h1d",
    ])
    def test_when_value_is_invalid(self, given: str):
        with pytest.raises(ValueError) as excinfo:
            _parse_timedelta_from_str(given)
        msg = 'string in a valid format required (e.g. "1d6h30m15s", "2h30m", "15m")'
        assert str(excinfo.value) == msg

    def test_non_string_value(self):
        given = object()
        result = _parse_timedelta_from_str(given)
        assert result is given


class TestDatabaseDSN:
    @pytest.mark.parametrize(["dsn", "expected"], [
        ("postgres://user:pass@localhost:5432/mydb", "postgres"),
        ("sqlite:///path/to/db.sqlite3", "sqlite"),
    ])
    def test_scheme(self, dsn: str, expected: str):
        assert DatabaseDSN(dsn).scheme == expected

    @pytest.mark.parametrize(["dsn", "expected"], [
        ("postgres://user:pass@localhost:5432/mydb", "mydb"),
        ("sqlite:///path/to/db.sqlite3", "path/to/db.sqlite3"),
    ])
    def test_name(self, dsn: str, expected: str):
        assert DatabaseDSN(dsn).name == expected

    @pytest.mark.parametrize(["dsn", "expected"], [
        ("sqlite:///:memory:", True),
        ("sqlite://:memory:", True),
        ("sqlite:///path/to/db.sqlite3", False),
        ("postgres://user:pass@localhost:5432/mydb", False),
    ])
    def test_is_memory(self, dsn: str, expected: bool):
        assert DatabaseDSN(dsn).is_memory() is expected

    @pytest.mark.parametrize(["dsn", "expected"], [
        ("sqlite:///path/to/db.sqlite3", True),
        ("sqlite:///:memory:", True),
        ("sqlite://:memory:", True),
        ("postgres://user:pass@localhost:5432/mydb", False),
    ])
    def test_is_sqlite(self, dsn: str, expected: bool):
        assert DatabaseDSN(dsn).is_sqlite() is expected

    def test_with_name(self):
        dsn = DatabaseDSN("postgres://user:pass@localhost:5432/mydb")
        result = dsn.with_name("mydb_test")
        assert result == "postgres://user:pass@localhost:5432/mydb_test"
        assert isinstance(result, DatabaseDSN)

    def test_with_name_preserves_query_params(self):
        dsn = DatabaseDSN(
            "sqlite:///path/to/db.sqlite3?install_regexp_functions=true"
        )
        result = dsn.with_name("/tmp/test/db.sqlite3")
        assert result == (
            "sqlite:///tmp/test/db.sqlite3?install_regexp_functions=true"
        )
        assert isinstance(result, DatabaseDSN)

    def test_with_name_without_query_params(self):
        dsn = DatabaseDSN("sqlite:///path/to/db.sqlite3")
        result = dsn.with_name("/tmp/test/db.sqlite3")
        assert result == "sqlite:///tmp/test/db.sqlite3"


class TestStoragesConfig:
    def test_media_storage_is_explicitly_provided(self):
        # GIVEN / WHEN
        config = StoragesConfig(
            default=FileSystemStorageConfig(fs_location="/shelf-storage"),
            media=FileSystemStorageConfig(fs_location="/shelf-media"),
        )
        # THEN
        assert config.media is not None
        assert config.media.type == StorageType.filesystem
        assert config.media.fs_location == "/shelf-media"

    def test_media_storage_fallbacks_to_default_filesystem_storage(self):
        # GIVEN / WHEN
        config = StoragesConfig(
            default=FileSystemStorageConfig(fs_location="/shelf-data/storage")
        )
        # THEN
        assert config.media is not None
        assert config.media.type == StorageType.filesystem
        assert config.media.fs_location == "/shelf-data/shelf-media"

    def test_media_storage_fallbacks_to_default_s3_storage(self):
        # GIVEN / WHEN
        config = StoragesConfig(
            default=S3StorageConfig(
                s3_location=AnyHttpUrl("http://localhost:9000"),
                s3_access_key_id="key",
                s3_secret_access_key="secret",
                s3_region="us-east-1",
                s3_bucket="shelf-data",
            )
        )
        # THEN
        assert config.media is not None
        assert config.media.type == StorageType.s3
        assert config.media.s3_bucket == "shelf-media"
