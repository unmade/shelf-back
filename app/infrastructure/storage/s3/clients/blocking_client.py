from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import (
    TYPE_CHECKING,
    overload,
)
from urllib.parse import quote
from xml.etree import ElementTree

from httpx import Client

from app.contrib.aws_v4_auth import AWSV4AuthFlow

from .constants import xmlns_re
from .exceptions import raise_for_status
from .models import S3File

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .models import S3ClientConfig

__all__ = [
    "S3Client",
]


class S3Client:
    __slots__ = ("base_url", "auth", "client")

    def __init__(self, config: S3ClientConfig):
        self.base_url = config.base_url
        self.auth = AWSV4AuthFlow(
            aws_access_key=config.access_key,
            aws_secret_key=config.secret_key,
            region=config.region,
            service="s3",
        )
        self.client = Client(
            auth=self.auth,
            event_hooks={"response": [raise_for_status]}
        )

    def _url(self, path: str) -> str:
        return f"{self.base_url}{quote(path)}"

    def head_object(self, bucket: str, key: str) -> S3File:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html
        """
        url = self._url(f"{bucket}/{key}")
        r = self.client.head(url)
        return S3File(
            key=key,
            last_modified=parsedate_to_datetime(r.headers["Last-Modified"]),
            size=int(r.headers["Content-Length"]),
            etag=r.headers["ETag"],
        )

    def iter_download(self, bucket: str, key: str) -> Iterator[bytes]:
        url = self._url(f"{bucket}/{key}")
        with self.client.stream("GET", url) as r:
            yield from r.iter_bytes()

    @overload
    def list_objects(
        self, bucket: str, prefix: str | None, *, delimiter: str
    ) -> Iterator[str | S3File]:
        ...

    @overload
    def list_objects(
        self, bucket: str, prefix: str | None, *, delimiter: None = None
    ) -> Iterator[S3File]:
        ...

    def list_objects(
        self, bucket: str, prefix: str | None, *, delimiter: str | None = None
    ) -> Iterator[str | S3File]:
        """
        List S3 files with the given prefix including common prefixes.

        https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html
        """

        assert prefix is None or not prefix.startswith("/"), (
            'the prefix to filter by should not start with "/"'
        )

        continuation_token = None

        while True:
            # WARNING! order is important here, params need to be in alphabetical order
            params = {
                "continuation-token": continuation_token,
                "delimiter": delimiter,
                "list-type": 2,
                "prefix": prefix,
            }
            params = {k: v for k, v in params.items() if v is not None}
            url = self._url(bucket)
            r = self.client.get(url, params=params)

            xml_root = ElementTree.fromstring(xmlns_re.sub(b"", r.content))
            for c in xml_root.findall("Contents"):
                yield S3File.from_xml(c)
            if (t := xml_root.find("IsTruncated")) is not None and t.text == "false":
                break

            if (t := xml_root.find("NextContinuationToken")) is not None:
                continuation_token = t.text
            else:
                raise RuntimeError(
                    f"unexpected response from S3:\n{r.content.decode()}"
                )
