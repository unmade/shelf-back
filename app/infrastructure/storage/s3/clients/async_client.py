from __future__ import annotations

import asyncio
import itertools
from contextlib import AsyncExitStack
from email.utils import parsedate_to_datetime
from typing import (
    IO,
    AsyncIterator,
    Self,
    overload,
)
from xml.etree import ElementTree

from httpx import AsyncClient

from app.contrib.aws_v4_auth import AWSV4AuthFlow

from .constants import xmlns, xmlns_re
from .exceptions import araise_for_status
from .models import S3ClientConfig, S3File

__all__ = [
    "AsyncS3Client",
]


class AsyncS3Client:
    __slots__ = ("base_url", "client", "auth", "_stack")

    def __init__(self, config: S3ClientConfig):
        self.base_url = config.base_url
        self.auth = AWSV4AuthFlow(
            aws_access_key=config.access_key,
            aws_secret_key=config.secret_key,
            region=config.region,
            service="s3",
        )
        self.client = AsyncClient(
            auth=self.auth,
            event_hooks={
                "response": [araise_for_status],
            },
        )
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self.client)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._stack.aclose()

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def copy_object(
        self, bucket: str, from_key: str | S3File, to_key: str | S3File
    ) -> None:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_CopyObject.html
        """
        url = self._url(f"{bucket}/{to_key}")
        headers = {"x-amz-copy-source": f"/{bucket}/{from_key}"}
        await self.client.put(url, headers=headers)

    async def create_bucket(self, name: str) -> None:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html
        """
        url = self._url(name)
        await self.client.put(url)

    async def delete_bucket(self, name: str) -> None:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_DeleteBucket.html
        """
        url = self._url(name)
        await self.client.delete(url)

    async def delete(self, bucket: str, *files: str | S3File) -> list[str]:
        """
        Delete one or more files, based on keys.
        """
        tasks = []
        chunk_size = 1000
        async with asyncio.TaskGroup() as tg:
            for i in range(0, len(files), chunk_size):
                tasks.append(
                    tg.create_task(
                        self._delete_1000_files(bucket, *files[i : i + chunk_size])
                    )
                )
        return list(itertools.chain.from_iterable(task.result() for task in tasks))

    async def delete_recursive(self, bucket: str, prefix: str | None) -> list[str]:
        """
        Delete files starting with a specific prefix.
        """
        files, tasks = [], []
        async with asyncio.TaskGroup() as tg:
            async for f in self.list_objects(bucket, prefix):
                files.append(f)
                if len(files) == 1000:
                    tasks.append(
                        tg.create_task(self._delete_1000_files(bucket, *files))
                    )
                    files = []

            if files:
                tasks.append(tg.create_task(self._delete_1000_files(bucket, *files)))
        return list(itertools.chain.from_iterable(task.result() for task in tasks))

    async def _delete_1000_files(self, bucket: str, *files: str | S3File) -> list[str]:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_DeleteObjects.html
        """
        assert len(files) <= 1000, (
            f"_delete_1000_files can delete 1000 files max, not {len(files)}"
        )
        xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<Delete xmlns="{xmlns}">'
            f' {"".join(f"<Object><Key>{file}</Key></Object>" for file in files)}'
            f"</Delete>"
        )
        data = xml.encode()
        url = self._url(bucket)
        r = await self.client.post(url, content=data, params={"delete": 1})
        xml_root = ElementTree.fromstring(xmlns_re.sub(b"", r.content))
        return [k.find("Key").text for k in xml_root]  # type: ignore

    async def head_object(self, bucket: str, key: str) -> S3File:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html
        """
        url = self._url(f"{bucket}/{key}")
        r = await self.client.head(url, auth=self.auth)
        return S3File(
            key=key,
            last_modified=parsedate_to_datetime(r.headers["Last-Modified"]),
            size=int(r.headers["Content-Length"]),
            etag=r.headers["ETag"],
        )

    async def iter_download(self, bucket: str, key: str) -> AsyncIterator[bytes]:
        url = self._url(f"{bucket}/{key}")
        async with self.client.stream("GET", url) as r:
            async for chunk in r.aiter_bytes():
                yield chunk

    @overload
    def list_objects(
        self, bucket: str, prefix: str | None, *, delimiter: str
    ) -> AsyncIterator[str | S3File]:
        ...

    @overload
    def list_objects(
        self, bucket: str, prefix: str | None, *, delimiter: None = None
    ) -> AsyncIterator[S3File]:
        ...

    async def list_objects(
        self, bucket: str, prefix: str | None, *, delimiter: str | None = None
    ) -> AsyncIterator[str | S3File]:
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
            url = self._url(bucket)
            params = {k: v for k, v in params.items() if v is not None}
            r = await self.client.get(url, params=params)
            xml_root = ElementTree.fromstring(xmlns_re.sub(b"", r.content))
            for c in xml_root.findall("CommonPrefixes"):
                for cp in c:
                    if cp.text:
                        yield cp.text
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

    async def put_object(self, bucket: str, key: str, data: IO[bytes]) -> S3File:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html
        """
        data.seek(0)
        content = data.read()
        size = len(content)

        url = self._url(f"{bucket}/{key}")
        headers = {"content-length": str(size)}

        r = await self.client.put(url, headers=headers, content=content)

        return S3File(
            key=key,
            last_modified=parsedate_to_datetime(r.headers["Date"]),
            size=size,
            etag=r.headers["ETag"],
        )
