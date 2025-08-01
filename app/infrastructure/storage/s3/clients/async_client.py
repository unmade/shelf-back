from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from email.utils import parsedate_to_datetime
from typing import (
    TYPE_CHECKING,
    Protocol,
    Self,
    overload,
)
from urllib.parse import quote
from xml.etree import ElementTree

from httpx import AsyncClient, Headers

from app.contrib.aws_v4_auth import AWSV4AuthFlow

from .constants import xmlns, xmlns_re
from .exceptions import araise_for_status
from .models import S3ClientConfig, S3File

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator

    class AsyncBytesReader(Protocol):
        size: int

        async def read(self, size: int = -1) -> bytes:
            ...

__all__ = [
    "AsyncS3Client",
]

_5_MB = 5 * 2**20


async def _aenumerate[T](
    iterable: AsyncIterable[T], start: int = 0
) -> AsyncIterator[tuple[int, T]]:
    n = start
    async for item in iterable:
        yield n, item
        n += 1


async def _readchunks(
    stream: AsyncBytesReader, *, chunk_size: int
) -> AsyncIterator[bytes]:
    has_content = True
    while has_content:
        chunk = await stream.read(chunk_size)
        has_content = len(chunk) == chunk_size
        yield chunk


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
            http2=True,
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
        return f"{self.base_url}{quote(path)}"

    async def copy_object(
        self, bucket: str, from_key: str | S3File, to_key: str | S3File
    ) -> None:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_CopyObject.html
        """
        url = self._url(f"{bucket}/{to_key}")
        headers = Headers({"x-amz-copy-source": f"/{bucket}/{from_key}"}, "utf-8")
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
        return [result for task in tasks for result in task.result()]

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

        return [result for task in tasks for result in task.result()]

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
            f'</Delete>'
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
        r = await self.client.head(url)
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

        contoken: str | None = None
        while True:
            # WARNING! order is important here, params need to be in alphabetical order
            params = {
                "continuation-token": contoken,
                "delimiter": delimiter,
                "list-type": 2,
                "prefix": prefix,
            }
            params = {k: v for k, v in params.items() if v is not None}
            url = self._url(bucket)
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
                contoken = t.text
            else:
                raise RuntimeError(
                    f"unexpected response from S3:\n{r.content.decode()}"
                )

    async def put_object(
        self, bucket: str, key: str, content: AsyncBytesReader
    ) -> S3File:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html
        """
        url = self._url(f"{bucket}/{key}")
        headers = {"content-length": str(content.size)}

        r = await self.client.put(url, headers=headers, content=await content.read())

        return S3File(
            key=key,
            last_modified=parsedate_to_datetime(r.headers["Date"]),
            size=content.size,
            etag=r.headers["ETag"],
        )

    async def upload_obj(
        self, bucket: str, key: str, content: AsyncBytesReader
    ) -> S3File:
        if content.size < _5_MB:
            return await self.put_object(bucket, key, content)

        chunk_size = max(_5_MB, content.size // (_5_MB * 10_000))

        url = self._url(f"{bucket}/{key}")
        chunks = _readchunks(content, chunk_size=chunk_size)
        async with (
            MultipartUpload(url, client=self.client) as mpu,
            asyncio.TaskGroup() as tg,
        ):
            async for n, chunk in _aenumerate(chunks, start=1):
                tg.create_task(mpu.upload_part(n, chunk))

        return mpu.result()


class MultipartUpload:
    __slots__ = ( "url", "client", "_semaphore", "_upload_id", "_parts", "_result")

    def __init__(self, url: str, *, client: AsyncClient, max_concurrency: int = 8):
        self.url = url
        self.client = client
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._upload_id: str | None = None
        self._parts: dict[int, tuple[str, int]] = {}
        self._result: S3File | None = None

    async def __aenter__(self) -> Self:
        await self.create()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_val:
            if self._upload_id is not None:
                await self.abort()
            raise

        if self._upload_id is not None:
            self._result = await self.complete()

    def result(self) -> S3File:
        assert self._result is not None, "Multipart upload not completed"
        return self._result

    async def abort(self) -> None:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_AbortMultipartUpload.html
        """
        assert self._upload_id is not None, "Multipart upload not started"
        params = {"uploadId": self._upload_id}
        await self.client.delete(self.url, params=params)

    async def complete(self) -> S3File:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html
        """
        assert self._upload_id is not None, "Multipart upload not started"
        xml_parts = "".join(
            f"<Part><PartNumber>{part}</PartNumber><ETag>{etag}</ETag></Part>"
            for part, (etag, _) in sorted(self._parts.items())
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<CompleteMultipartUpload xmlns="{xmlns}">'
            f'  {xml_parts}'
            '</CompleteMultipartUpload>'
        )
        data = xml.encode()
        params = {"uploadId": self._upload_id}
        r = await self.client.post(self.url, content=data, params=params)
        xml_root = ElementTree.fromstring(xmlns_re.sub(b'', r.content))
        return S3File(
            key=xml_root.find("Key").text,  # type: ignore[union-attr, arg-type]
            last_modified=parsedate_to_datetime(r.headers["Date"]),
            size=sum(v[1] for v in self._parts.values()),
            etag=xml_root.find("ETag").text,  # type: ignore[union-attr, arg-type]
        )

    async def create(self) -> None:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateMultipartUpload.html
        """
        r = await self.client.post(self.url, params={"uploads": ""})

        xml_root = ElementTree.fromstring(xmlns_re.sub(b'', r.content))
        upload_id = xml_root.find('UploadId')
        assert upload_id is not None, "`UploadId` not found"
        self._upload_id = upload_id.text

    async def upload_part(self, part_number: int, content: bytes) -> None:
        """
        https://docs.aws.amazon.com/AmazonS3/latest/API/API_UploadPart.html
        """
        assert self._upload_id is not None, "Multipart upload not started"
        size = len(content)

        headers = {"content-length": str(size)}
        params = {
            "partNumber": str(part_number),
            "uploadId": self._upload_id,
        }
        async with self._semaphore:
            r = await self.client.put(
                self.url, headers=headers, params=params, content=content
            )
        self._parts[part_number] = r.headers["ETag"], size
