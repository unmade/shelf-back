from __future__ import annotations

import datetime
import os
import os.path
from typing import IO, TYPE_CHECKING, Iterator

import boto3
import stream_zip
from asgiref.sync import sync_to_async
from botocore.client import Config
from botocore.exceptions import ClientError

from app import config
from app.app.files.domain import File
from app.app.infrastructure.storage import ContentReader, IStorage, StorageFile

from ._compat import iter_async
from ._datastructures import StreamZipFile

if TYPE_CHECKING:
    from botocore.response import StreamingBody

    from app.app.files.domain import AnyPath

__all__ = ["S3Storage"]


class S3Storage(IStorage):
    def __init__(self, location: AnyPath):
        assert config.STORAGE_S3_ACCESS_KEY_ID is not None
        assert config.STORAGE_S3_SECRET_ACCESS_KEY is not None
        assert config.STORAGE_S3_REGION_NAME is not None
        self.location = str(location)
        self.bucket_name = config.STORAGE_S3_BUCKET_NAME
        self.s3 = boto3.resource(
            "s3",
            endpoint_url=self.location,
            aws_access_key_id=config.STORAGE_S3_ACCESS_KEY_ID,
            aws_secret_access_key=config.STORAGE_S3_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name=config.STORAGE_S3_REGION_NAME,
        )

    def _joinpath(self, ns_path: AnyPath, path: AnyPath) -> str:
        return os.path.normpath(os.path.join(str(ns_path), str(path)))

    @property
    def bucket(self):
        return self.s3.Bucket(self.bucket_name)

    @sync_to_async
    def delete(self, ns_path: AnyPath, path: AnyPath) -> None:
        key = self._joinpath(ns_path, path)
        self.s3.Object(self.bucket_name, key).delete()

    @sync_to_async
    def deletedir(self, ns_path: AnyPath, path: AnyPath) -> None:
        prefix = f"{self._joinpath(ns_path, path)}/"
        self.bucket.objects.filter(Prefix=prefix).delete()

    async def emptydir(self, ns_path: AnyPath, path: AnyPath) -> None:
        await self.deletedir(ns_path, path)

    async def download(self, ns_path: AnyPath, path: AnyPath) -> ContentReader:
        stream = await self._download(ns_path, path)
        return ContentReader(iter_async(stream.iter_chunks(4096)), zipped=False)

    @sync_to_async
    def _download(self, ns_path: AnyPath, path: AnyPath) -> StreamingBody:
        key = self._joinpath(ns_path, path)

        try:
            obj = self.s3.Object(self.bucket_name, key).get()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                raise File.NotFound() from exc
            raise

        return obj["Body"]

    async def downloaddir(self, ns_path: AnyPath, path: AnyPath) -> ContentReader:
        archive = stream_zip.stream_zip(self._downloaddir_iter(ns_path, path))
        return ContentReader(iter_async(archive), zipped=True)

    def _downloaddir_iter(
        self,
        ns_path: AnyPath,
        path: AnyPath,
    ) -> Iterator[StreamZipFile]:
        ns_path = str(ns_path)
        fullpath = self._joinpath(ns_path, path)
        prefix = f"{fullpath}/"

        paginator = self.s3.meta.client.get_paginator("list_objects")
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
        for page in pages:
            for entry in page.get("Contents", ()):
                if entry["Key"] != prefix:
                    obj = self.s3.Object(self.bucket_name, entry["Key"]).get()
                    yield StreamZipFile(
                        path=os.path.relpath(entry["Key"], fullpath),
                        modified_at=entry["LastModified"],
                        perms=0o600,
                        compression=stream_zip.ZIP_32,
                        content=obj["Body"],
                    )

    @sync_to_async
    def exists(self, ns_path: AnyPath, path: AnyPath) -> bool:
        key = self._joinpath(ns_path, path)

        try:
            self.s3.Object(self.bucket_name, key).load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                collection = self.bucket.objects.filter(Prefix=f"{key}/").limit(1)
                return any(collection)
            raise

        return True

    @sync_to_async
    def get_modified_time(self, ns_path: AnyPath, path: AnyPath) -> float:
        key = self._joinpath(ns_path, path)
        obj = self.s3.Object(self.bucket_name, key)

        try:
            obj.load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise File.NotFound() from exc
            raise

        return obj.last_modified.timestamp()

    @sync_to_async
    def iterdir(self, ns_path: AnyPath, path: AnyPath) -> Iterator[StorageFile]:
        ns_path = str(ns_path)
        bucket_name = self.bucket_name
        prefix = f"{self._joinpath(ns_path, path)}/"

        paginator = self.s3.meta.client.get_paginator("list_objects")
        pages = paginator.paginate(Bucket=bucket_name, Delimiter="/", Prefix=prefix)
        for page in pages:
            for folder in page.get("CommonPrefixes", ()):
                key = folder["Prefix"].strip("/")
                yield StorageFile(
                    name=os.path.basename(key),
                    ns_path=ns_path,
                    path=key[len(ns_path) + 1:],
                    size=0,
                    mtime=0,
                    is_dir=True,
                )
            for file in page.get("Contents", ()):
                if file["Key"] != prefix:
                    yield StorageFile(
                        name=os.path.basename(file["Key"]),
                        ns_path=ns_path,
                        path=file["Key"][len(ns_path) + 1:],
                        size=file["Size"],
                        mtime=file["LastModified"].timestamp(),
                        is_dir=False,
                    )

    @sync_to_async
    def makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        return None

    @sync_to_async
    def move(
        self,
        ns_path: AnyPath,
        from_path: AnyPath,
        to_path: AnyPath
    ) -> None:
        from_key = self._joinpath(ns_path, from_path)
        to_key = self._joinpath(ns_path, to_path)
        self._move(from_key, to_key)

    @sync_to_async
    def movedir(
        self,
        ns_path: AnyPath,
        from_path: AnyPath,
        to_path: AnyPath
    ) -> None:
        from_prefix = f"{self._joinpath(ns_path, from_path)}/"
        to_prefix = f"{self._joinpath(ns_path, to_path)}/"

        collection = list(self.bucket.objects.filter(Prefix=from_prefix))
        for entry in collection:
            rel_key = os.path.relpath(entry.key, from_prefix)
            new_key = os.path.normpath(os.path.join(to_prefix, rel_key))
            self._move(entry.key, new_key)

    def _move(
        self,
        from_key: str,
        to_key: str,
    ) -> None:
        obj = self.s3.Object(self.bucket_name, to_key)

        try:
            obj.copy({"Bucket": self.bucket_name, "Key": from_key})
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise File.NotFound() from exc
            raise

        self.s3.Object(self.bucket_name, from_key).delete()

    @sync_to_async
    def save(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        content: IO[bytes],
    ) -> StorageFile:
        key = self._joinpath(ns_path, path)

        content.seek(0)
        size = content.seek(0, 2)
        content.seek(0)

        self.bucket.upload_fileobj(content, key)

        return StorageFile(
            name=os.path.basename(str(path)),
            ns_path=str(ns_path),
            path=str(path),
            size=size,
            mtime=datetime.datetime.now().timestamp(),
            is_dir=False,
        )

    @sync_to_async
    def size(self, ns_path: AnyPath, path: AnyPath) -> int:
        key = self._joinpath(ns_path, path)
        obj = self.s3.Object(self.bucket_name, key)

        try:
            obj.load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise File.NotFound() from exc
            raise

        return obj.content_length
