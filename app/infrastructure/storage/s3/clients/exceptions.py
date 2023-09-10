from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree import ElementTree

if TYPE_CHECKING:
    from httpx import Response

__all__ = [
    "S3Error",
    "BucketAlreadyExists",
    "BucketAlreadyOwnedByYou",
    "NoSuchKey",
    "ResourceNotFound",
    "raise_for_status",
    "araise_for_status",
]


class S3Error(Exception):
    pass


class AccessDenied(S3Error):
    pass


class BucketAlreadyExists(S3Error):
    pass


class BucketAlreadyOwnedByYou(S3Error):
    pass


class NoSuchKey(S3Error):
    pass


class ResourceNotFound(S3Error):
    pass


ERROR_CODES = {
    "AccessDenied": AccessDenied,
    "BucketAlreadyOwnedByYou": BucketAlreadyOwnedByYou,
    "BucketAlreadyExists": BucketAlreadyExists,
    "NoSuchKey": NoSuchKey,
}


def raise_for_status(response: Response) -> None:
    if response.is_success:
        return

    content = response.read()
    try:
        error = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        pass
    else:
        code = error.find("Code")
        if code is not None and code.text in ERROR_CODES:
            raise ERROR_CODES[code.text]

    if response.status_code == 404:
        raise ResourceNotFound() from None

    response.raise_for_status()


async def araise_for_status(response: Response) -> None:
    if response.is_success:
        return

    content = await response.aread()
    try:
        error = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        pass
    else:
        code = error.find("Code")
        if code is not None and code.text in ERROR_CODES:
            raise ERROR_CODES[code.text]

    if response.status_code == 404:
        raise ResourceNotFound() from None

    response.raise_for_status()
