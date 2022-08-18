import pytest

from app import mediatypes


def test_guess_based_on_file_content() -> None:
    jpeg_header = b'\xff\xd8\xff\xe0\x00\x10'
    assert mediatypes.guess("image", content=jpeg_header) == "image/jpeg"


def test_guess_based_on_filename() -> None:
    assert mediatypes.guess("f.txt") == "text/plain"


def test_guess_based_on_file_content_with_fallback_to_filename() -> None:
    assert mediatypes.guess("f.txt", content=b"dummy") == "text/plain"


@pytest.mark.parametrize(["unsafe", "expected"], [
    (False, mediatypes.OCTET_STREAM),
    (True, "image/jpeg")
])
def test_guess_unsafe(unsafe: bool, expected: str):
    assert mediatypes.guess("f.jpg", unsafe=unsafe) == expected


def test_guess_but_filename_does_not_have_suffix() -> None:
    assert mediatypes.guess("f") == mediatypes.OCTET_STREAM


@pytest.mark.parametrize(["mediatype", "image"], [
    ("image/jpeg", True),
    ("image/png", True),
    ("image/x-icon", True),
    ("image/svg", False),
])
def test_is_image(mediatype: str, image: bool):
    assert mediatypes.is_image(mediatype) is image
