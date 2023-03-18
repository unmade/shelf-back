from __future__ import annotations

import uuid
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from app import actions, errors

if TYPE_CHECKING:

    from app.entities import Namespace
    from app.typedefs import DBClient
    from tests.factories import (
        FileFactory,
        FolderFactory,
        NamespaceFactory,
    )

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


async def test_get_thumbnail(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    image_content: BytesIO,
):
    file = await file_factory(namespace.path, content=image_content)

    filecache, thumbnail = (
        await actions.get_thumbnail(db_client, namespace, file.id, size=64)
    )
    assert filecache == file
    assert len(thumbnail) < file.size
    assert isinstance(thumbnail, bytes)


async def test_get_thumbnail_but_file_not_found(
    db_client: DBClient,
    namespace: Namespace,
):
    file_id = uuid.uuid4()
    with pytest.raises(errors.FileNotFound):
        await actions.get_thumbnail(db_client, namespace, file_id, size=24)


async def test_get_thumbnail_but_file_in_other_namespace(
    db_client: DBClient,
    namespace_factory: NamespaceFactory,
    file_factory: FileFactory,
):
    namespace_a = await namespace_factory()
    namespace_b = await namespace_factory()
    file = await file_factory(namespace_b.path)
    with pytest.raises(errors.FileNotFound):
        await actions.get_thumbnail(db_client, namespace_a, file.id, size=24)


async def test_get_thumbnail_but_file_is_a_directory(
    db_client: DBClient,
    namespace: Namespace,
    folder_factory: FolderFactory,
):
    folder = await folder_factory(namespace.path)
    with pytest.raises(errors.IsADirectory):
        await actions.get_thumbnail(db_client, namespace, folder.id, size=64)


async def test_get_thumbnail_but_file_is_a_text_file(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    with pytest.raises(errors.ThumbnailUnavailable):
        await actions.get_thumbnail(db_client, namespace, file.id, size=64)


async def test_get_thumbnail_but_file_is_not_thumbnailable(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    with pytest.raises(errors.ThumbnailUnavailable):
        await actions.get_thumbnail(db_client, namespace, file.id, size=64)
