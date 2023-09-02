from __future__ import annotations

import asyncio
import itertools
from email.utils import parsedate_to_datetime
from typing import IO, TYPE_CHECKING, AsyncIterator, overload
from xml.etree import ElementTree

from aioaws._utils import pretty_xml
from aioaws.core import AwsClient, RequestError
from aioaws.s3 import S3File, to_key, xmlns, xmlns_re
from httpx import URL

if TYPE_CHECKING:
    from aioaws._types import S3ConfigProtocol
    from httpx import AsyncClient

__all__ = ["AsyncS3Client"]


class NoSuchKey(Exception):
    pass


class AsyncS3Client:
    __slots__ = '_config', '_aws_client'

    def __init__(self, http_client: AsyncClient, config: S3ConfigProtocol):
        self._aws_client = AwsClient(http_client, config, 's3')
        self._config = config

    async def copy_object(
        self, bucket: str, from_key: str | S3File, to_key: str | S3File
    ) -> None:
        path = f"{bucket}/{to_key}"
        url = URL(f'{self._aws_client.endpoint}/{path}')
        headers = self._aws_client._auth.auth_headers(
            method="PUT",  # type: ignore[arg-type]
            url=url,
        )
        headers["x-amz-copy-source"] = f"/{bucket}/{from_key}"
        r = await self._aws_client.client.put(url=url, headers=headers)
        if r.status_code != 200:
            if r.status_code == 404:
                raise NoSuchKey() from None
            raise RequestError(r) from None

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

    async def delete_recursive(self, bucket: str, prefix: str) -> list[str]:
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
            f' {"".join(f"<Object><Key>{to_key(k)}</Key></Object>" for k in files)}'
            f"</Delete>"
        )
        r = await self._aws_client.post(
            f"/{bucket}",
            data=xml.encode(),
            params={"delete": 1},
            content_type="text/xml",
        )
        xml_root = ElementTree.fromstring(xmlns_re.sub(b"", r.content))
        return [k.find("Key").text for k in xml_root]  # type: ignore

    async def head_object(self, bucket: str, key: str) -> S3File:
        path = "/".join([f"/{bucket}", key])
        try:
            r = await self._aws_client.request(
                "HEAD",  # type: ignore[arg-type]
                path=path,
                params=None,
            )
        except RequestError as exc:
            if exc.status == 404:
                raise NoSuchKey() from exc
            raise
        return S3File.model_construct(
            key=key,
            last_modified=parsedate_to_datetime(r.headers["Last-Modified"]),
            size=int(r.headers["Content-Length"]),
            e_tag=r.headers["ETag"],
            storage_class=r.headers["Server"],
        )

    async def iter_download(self, bucket: str, key: str) -> AsyncIterator[bytes]:
        path = f"{bucket}/{key}"
        url = URL(f'{self._aws_client.endpoint}/{path}')
        headers = self._aws_client._auth.auth_headers("GET", url)
        async with self._aws_client.client.stream("GET", url, headers=headers) as r:
            if r.status_code != 200:
                if r.status_code == 404:
                    raise NoSuchKey() from None
                raise RequestError(r)

            async for chunk in r.aiter_bytes():
                yield chunk

    @overload
    def list_objects(
        self, bucket: str, prefix: str, *, delimiter: str
    ) -> AsyncIterator[str | S3File]:
        ...

    @overload
    def list_objects(
        self, bucket: str, prefix: str, *, delimiter: None = None
    ) -> AsyncIterator[S3File]:
        ...

    async def list_objects(
        self, bucket: str, prefix: str, *, delimiter: str | None = None
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
            params = {
                "list-type": 2,
                "prefix": prefix,
                "delimiter": delimiter,
                "continuation-token": continuation_token,
            }
            params = {k: v for k, v in params.items() if v is not None}
            r = await self._aws_client.get(f"/{bucket}", params=params)

            xml_root = ElementTree.fromstring(xmlns_re.sub(b"", r.content))
            for c in xml_root.findall("CommonPrefixes"):
                for cp in c:
                    if cp.text:
                        yield cp.text
            for c in xml_root.findall("Contents"):
                yield S3File.model_validate({v.tag: v.text for v in c})
            if (t := xml_root.find("IsTruncated")) is not None and t.text == "false":
                break

            if (t := xml_root.find("NextContinuationToken")) is not None:
                continuation_token = t.text
            else:
                raise RuntimeError(
                    f"unexpected response from S3:\n{pretty_xml(r.content)}"
                )

    async def put_object(self, bucket: str, key: str, data: IO[bytes]) -> S3File:
        async def async_iter(buf):
            for chunk in buf:
                yield chunk

        data.seek(0)
        size = data.seek(0, 2)
        data.seek(0)

        path = f"{bucket}/{key}"
        url = URL(f'{self._aws_client.endpoint}/{path}')
        headers = self._aws_client._auth.auth_headers(
            method="PUT",  # type: ignore[arg-type]
            url=url,
            data=data.read(),
        )
        headers["content-length"] = str(size)
        data.seek(0)
        r = await self._aws_client.client.put(
            url, headers=headers, content=async_iter(data)
        )
        if r.status_code != 200:
            raise RequestError(r) from None

        return S3File.model_construct(
            key=key,
            last_modified=parsedate_to_datetime(r.headers["Date"]),
            size=size,
            e_tag=r.headers["ETag"],
            storage_class=r.headers["Server"],
        )
