from __future__ import annotations

from io import BytesIO

from app.app.files.domain import mediatypes


class TestGuess:
    def test_on_jpeg_image(self) -> None:
        jpeg_header = BytesIO(b'\xff\xd8\xff\xe0\x00\x10')
        assert mediatypes.guess(jpeg_header) == "image/jpeg"

    def test_on_unknown_content(self) -> None:
        content = BytesIO(b"Dummy")
        assert mediatypes.guess(content) == mediatypes.OCTET_STREAM

    def test_fallback_to_filename_for_unknown_content(self):
        content = BytesIO(b"dummy")
        assert mediatypes.guess(content, name="f.txt") == "text/plain"

    def test_no_fallback_to_filename_for_strict_extension(self):
        content = BytesIO(b"dummy")
        assert mediatypes.guess(content, name="im.jpeg") == mediatypes.OCTET_STREAM


class TestGuessUnsafe:
    def test_on_jpeg_image(self) -> None:
        assert mediatypes.guess_unsafe("img.jpeg") == "image/jpeg"

    def test_when_no_extenstion(self) -> None:
        assert mediatypes.guess_unsafe("f") == mediatypes.OCTET_STREAM
