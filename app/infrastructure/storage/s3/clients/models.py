from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

__all__ = [
    "S3File",
    "S3ClientConfig",
]


class S3File:
    __slots__ = ("key", "last_modified", "size", "etag")

    def __init__(self, key: str, last_modified: datetime, size: int, etag: str):
        self.key = key
        self.last_modified = last_modified
        self.size = size
        self.etag = etag

    def __str__(self) -> str:
        return self.key

    @classmethod
    def from_xml(cls, node: Element) -> Self:

        return cls(
            key=node.find("Key").text,  # type: ignore[union-attr, arg-type]
            last_modified=datetime.fromisoformat(
                node.find("LastModified").text  # type: ignore[union-attr, arg-type]
            ),
            size=int(node.find("Size").text),  # type: ignore[union-attr, arg-type]
            etag=node.find("ETag").text,  # type: ignore[union-attr, arg-type]
        )


@dataclass(slots=True)
class S3ClientConfig:
    base_url: str
    access_key: str
    secret_key: str
    region: str
