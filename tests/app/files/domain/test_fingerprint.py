from __future__ import annotations

import uuid

from faker import Faker

from app.app.files.domain import Fingerprint

fake = Faker()


class TestEQ:
    def test_comparing_two_equal(self):
        file_id = uuid.uuid4()
        value = 16493668159829433821
        a = Fingerprint(file_id=file_id, value=value)
        b = Fingerprint(file_id=file_id, value=value)
        assert a == b

    def test_comparing_two_non_equal(self):
        value = 16493668159829433821
        a = Fingerprint(file_id=uuid.uuid4(), value=value)
        b = Fingerprint(file_id=uuid.uuid4(), value=value)
        assert a != b

    def test_comparing_fingerprint_with_another_object_always_false(self):
        fp = Fingerprint(file_id=uuid.uuid4(), value=16493668159829433821)
        assert (fp == {}) is False


class TestHash:
    def test_hashes_are_the_same_for_equal_fingerprints(self) -> None:
        file_id = uuid.uuid4()
        value = 16493668159829433821
        a = Fingerprint(file_id=file_id, value=value)
        b = Fingerprint(file_id=file_id, value=value)
        assert hash(a) == hash(b)

    def test_hashes_are_the_different_for_non_equal_fingerprints(self) -> None:
        value = 16493668159829433821
        a = Fingerprint(file_id=uuid.uuid4(), value=value)
        b = Fingerprint(file_id=uuid.uuid4(), value=value)
        assert hash(a) != hash(b)


class TestRepr:
    def test(self) -> None:
        file_id = uuid.uuid4()
        value = 16493668159829433821
        fp = Fingerprint(file_id=file_id, value=value)
        assert repr(fp) == f"Fingerprint(file_id='{file_id}', value={value})"
