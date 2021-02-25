from app import mediatypes


def test_guess_based_on_file_content():
    jpeg_header = b'\xff\xd8\xff\xe0\x00\x10'
    assert mediatypes.guess("image", file=jpeg_header) == "image/jpeg"


def test_guess_based_on_filename():
    assert mediatypes.guess("f.txt") == "text/plain"


def test_guess_based_on_file_content_with_fallback_to_filename():
    assert mediatypes.guess("f.txt", file=b"dummy") == "text/plain"


def test_guess_but_filename_does_not_have_suffix():
    assert mediatypes.guess("f") == mediatypes.OCTET_STREAM
