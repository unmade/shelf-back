from __future__ import annotations

import asyncio
import os
import os.path
from typing import IO, TYPE_CHECKING, AsyncIterator, Iterator

import httpx
from aioaws.s3 import S3Config, S3File
import stream_zip

from app.app.files.domain import File
from app.app.infrastructure.storage import ContentReader, StorageFile
from app.config import S3StorageConfig

from .._datastructures import StreamZipFile

from .client import AsyncS3Client, NoSuchKey

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath

__all__ = ["AsyncS3Storage"]


class AsyncS3Storage:
    def __init__(self, config: S3StorageConfig):
        client = httpx.AsyncClient()
        netloc = ":".join([str(config.s3_location.host), str(config.s3_location.port)])
        self.s3 = AsyncS3Client(
            client,
            S3Config(
                aws_host=netloc,
                aws_access_key=config.s3_access_key_id,
                aws_secret_key=config.s3_secret_access_key,
                aws_region=config.s3_region,
                aws_s3_bucket=config.s3_bucket,
            ),
        )
        self.s3._aws_client.schema = config.s3_location.scheme
        self.location = str(config.s3_location)
        self.bucket_name = config.s3_bucket

    def _joinpath(self, ns_path: AnyPath, path: AnyPath) -> str:
        return os.path.normpath(os.path.join(str(ns_path), str(path)))

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> None:
        key = self._joinpath(ns_path, path)
        await self.s3.delete(self.bucket_name, key)

    async def deletedir(self, ns_path: AnyPath, path: AnyPath) -> None:
        prefix = f"{self._joinpath(ns_path, path)}/"
        await self.s3.delete_recursive(self.bucket_name, prefix)

    async def emptydir(self, ns_path: AnyPath, path: AnyPath) -> None:
        await self.deletedir(ns_path, path)

    async def exists(self, ns_path: AnyPath, path: AnyPath) -> bool:
        key = self._joinpath(ns_path, path)
        try:
            await self.s3.head_object(self.bucket_name, key)
        except NoSuchKey:
            return False
        return True

    def download(self, ns_path: AnyPath, path: AnyPath) -> ContentReader:
        key = self._joinpath(ns_path, path)
        content_iterator = self.s3.iter_download(self.bucket_name, key)
        return ContentReader(content_iterator, zipped=False)

    def downloaddir(self, ns_path: AnyPath, path: AnyPath) -> Iterator[bytes]:
        prefix = self._joinpath(ns_path, path)
        return stream_zip.stream_zip(
            StreamZipFile(
                path=os.path.relpath(entry.key, prefix),
                modified_at=entry.last_modified,
                perms=0o600,
                compression=stream_zip.ZIP_32,
                content=self._download_sync(entry.key),
            )
            for entry in self._iterdir_sync(ns_path, path)
        )

    def _download_sync(self, key: str):
        path = f"{self.bucket_name}/{key}"
        url = httpx.URL(f'{self.s3._aws_client.endpoint}/{path}')
        headers = self.s3._aws_client._auth.auth_headers("GET", url)
        with httpx.stream("GET", url, headers=headers) as r:
            if r.status_code != 200:
                if r.status_code == 404:
                    raise NoSuchKey() from None
                r.raise_for_status()
            for chunk in r.iter_bytes():
                yield chunk

    def _iterdir_sync(self, ns_path: AnyPath, path: AnyPath):
        from xml.etree import ElementTree
        from aioaws._utils import pretty_xml
        from aioaws.s3 import S3File, xmlns_re

        prefix = f"{self._joinpath(ns_path, path)}/"
        continuation_token = None

        while True:
            params = {
                "list-type": 2,
                "prefix": prefix,
                "continuation-token": continuation_token,
            }
            params = {k: v for k, v in params.items() if v is not None}
            url = httpx.URL(
                f'{self.s3._aws_client.endpoint}/{self.bucket_name}',
                params=[(k, v) for k, v in sorted((params or {}).items())]
            )
            headers = self.s3._aws_client._auth.auth_headers("GET", url)
            r = httpx.get(url, headers=headers)

            xml_root = ElementTree.fromstring(xmlns_re.sub(b"", r.content))
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

    async def iterdir(
        self, ns_path: AnyPath, path: AnyPath
    ) -> AsyncIterator[StorageFile]:
        ns_path = str(ns_path)
        prefix = f"{self._joinpath(ns_path, path)}/"
        async for item in self.s3.list_objects(self.bucket_name, prefix, delimiter="/"):
            if isinstance(item, S3File):
                yield StorageFile(
                    name=os.path.basename(item.key),
                    ns_path=ns_path,
                    path=item.key[len(ns_path) + 1:],
                    size=item.size,
                    mtime=item.last_modified.timestamp(),
                    is_dir=False,
                )
            else:
                key = item.strip("/")
                yield StorageFile(
                    name=os.path.basename(key),
                    ns_path=ns_path,
                    path=key[len(ns_path) + 1:],
                    size=0,
                    mtime=0,
                    is_dir=True,
                )

    async def makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        return None

    async def move(
        self, at: tuple[AnyPath, AnyPath], to: tuple[AnyPath, AnyPath]
    ) -> None:
        from_key = self._joinpath(*at)
        to_key = self._joinpath(*to)
        try:
            await self.s3.copy_object(self.bucket_name, from_key, to_key)
        except NoSuchKey as exc:
            raise File.NotFound() from exc
        await self.s3.delete(self.bucket_name, from_key)

    async def movedir(
        self, at: tuple[AnyPath, AnyPath], to: tuple[AnyPath, AnyPath]
    ) -> None:
        from_prefix = f"{self._joinpath(*at)}/"
        to_prefix = f"{self._joinpath(*to)}/"
        keys_to_delete = []
        async with asyncio.TaskGroup() as tg:
            async for entry in self.s3.list_objects(self.bucket_name, from_prefix):
                rel_key = os.path.relpath(entry.key, from_prefix)
                new_key = os.path.normpath(os.path.join(to_prefix, rel_key))
                keys_to_delete.append(entry.key)
                tg.create_task(
                    self.s3.copy_object(self.bucket_name, entry.key, new_key)
                )
        await self.s3.delete(self.bucket_name, *keys_to_delete)

    async def save(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        content: IO[bytes],
    ) -> StorageFile:
        key = self._joinpath(ns_path, path)
        file = await self.s3.put_object(self.bucket_name, key, content)
        return StorageFile(
            name=os.path.basename(str(path)),
            ns_path=str(ns_path),
            path=str(path),
            size=file.size,
            mtime=file.last_modified.timestamp(),
            is_dir=False,
        )
