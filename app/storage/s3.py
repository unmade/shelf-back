from __future__ import annotations

import datetime
import os
import os.path
from io import BytesIO
from typing import IO, TYPE_CHECKING, Iterator

import boto3
from asgiref.sync import sync_to_async
from botocore.client import Config
from botocore.exceptions import ClientError
from PIL import Image, UnidentifiedImageError
from PIL.ImageOps import exif_transpose

from app import config, errors

from .base import Storage, StorageFile

if TYPE_CHECKING:
    from app.typedefs import StrOrPath


class S3Storage(Storage):
    def __init__(self, location: StrOrPath):
        assert config.S3_STORAGE_ACCESS_KEY_ID is not None
        assert config.S3_STORAGE_SECRET_ACCESS_KEY is not None
        assert config.S3_STORAGE_REGION_NAME is not None
        super().__init__(location)
        self.bucket_name = config.S3_STORAGE_BUCKET_NAME
        self.s3 = boto3.resource(
            "s3",
            endpoint_url=self.location,
            aws_access_key_id=config.S3_STORAGE_ACCESS_KEY_ID,
            aws_secret_access_key=config.S3_STORAGE_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name=config.S3_STORAGE_REGION_NAME,
        )

    def _joinpath(self, ns_path: StrOrPath, path: StrOrPath) -> str:
        return os.path.normpath(os.path.join(ns_path, path))

    @property
    def bucket(self):
        return self.s3.Bucket(self.bucket_name)

    @staticmethod
    def _readchunks(stream) -> Iterator[bytes]:
        chunk_size = 4096
        has_content = True
        while has_content:
            chunk = stream.read(chunk_size)
            has_content = len(chunk) == chunk_size
            yield chunk

    @sync_to_async
    def delete(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        key = self._joinpath(ns_path, path)
        obj = self.s3.Object(self.bucket_name, key)

        try:
            obj.load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                self.bucket.objects.filter(Prefix=f"{key}/").delete()
                return
            raise
        else:
            obj.delete()

    def download(self, ns_path: StrOrPath, path: StrOrPath) -> Iterator[bytes]:
        key = self._joinpath(ns_path, path)

        try:
            obj = self.s3.Object(self.bucket_name, key).get()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                raise errors.FileNotFound() from exc
            raise

        return self._readchunks(obj["Body"])

    @sync_to_async
    def exists(self, ns_path: StrOrPath, path: StrOrPath) -> bool:
        key = self._joinpath(ns_path, path)

        try:
            self.s3.Object(self.bucket_name, key).load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                collection = self.bucket.objects.filter(Prefix=f"{key}/").limit(1)
                return len(list(collection)) > 0
            raise

        return True

    @sync_to_async
    def get_modified_time(self, ns_path: StrOrPath, path: StrOrPath) -> float:
        key = self._joinpath(ns_path, path)
        obj = self.s3.Object(self.bucket_name, key)

        try:
            obj.load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise errors.FileNotFound() from exc
            raise

        return obj.last_modified.timestamp()

    @sync_to_async
    def iterdir(self, ns_path: StrOrPath, path: StrOrPath) -> Iterator[StorageFile]:
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
    def makedirs(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        return None

    @sync_to_async
    def move(
        self,
        ns_path: StrOrPath,
        from_path: StrOrPath,
        to_path: StrOrPath
    ) -> None:
        from_key = self._joinpath(ns_path, from_path)
        to_key = self._joinpath(ns_path, to_path)
        obj = self.s3.Object(self.bucket_name, to_key)

        try:
            obj.copy({"Bucket": self.bucket_name, "Key": from_key})
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise errors.FileNotFound() from exc
            raise

        try:
            self.s3.Object(self.bucket_name, from_key).delete()
        except ClientError:
            raise

    @sync_to_async
    def save(
        self,
        ns_path: StrOrPath,
        path: StrOrPath,
        content: IO[bytes],
    ) -> StorageFile:
        key = self._joinpath(ns_path, path)

        content.seek(0)
        size = content.seek(0, 2)
        content.seek(0)

        self.bucket.upload_fileobj(content, key)

        return StorageFile(
            name=os.path.basename(path),
            ns_path=str(ns_path),
            path=str(path),
            size=size,
            mtime=datetime.datetime.now().timestamp(),
            is_dir=False,
        )

    @sync_to_async
    def size(self, ns_path: StrOrPath, path: StrOrPath) -> int:
        key = self._joinpath(ns_path, path)
        obj = self.s3.Object(self.bucket_name, key)

        try:
            obj.load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise errors.FileNotFound() from exc
            raise

        return obj.content_length

    @sync_to_async
    def thumbnail(
        self,
        ns_path: StrOrPath,
        path: StrOrPath,
        size: int,
    ) -> tuple[int, IO[bytes]]:
        key = self._joinpath(ns_path, path)
        content = BytesIO()

        try:
            self.bucket.download_fileobj(key, content)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                raise errors.FileNotFound() from exc
            raise

        buffer = BytesIO()
        try:
            with Image.open(content) as im:
                im.thumbnail((size, size))
                exif_transpose(im).save(buffer, im.format)
        except UnidentifiedImageError as exc:
            msg = f"Can't generate a thumbnail for a file: '{path}'"
            raise errors.ThumbnailUnavailable(msg) from exc

        size = buffer.seek(0, 2)
        buffer.seek(0)

        return size, buffer
