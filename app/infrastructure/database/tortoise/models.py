from __future__ import annotations

from uuid import uuid7

from tortoise import fields, models


class Account(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.ForeignKeyRelation[User] = fields.OneToOneField(
        "models.User", related_name="account", on_delete=fields.CASCADE,
    )
    storage_quota = fields.BigIntField(null=True)


class AuditTrailAction(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    name = fields.CharField(max_length=255, unique=True)


class Album(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    title = fields.CharField(max_length=255)
    slug = fields.CharField(max_length=255)
    owner: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="albums", on_delete=fields.CASCADE,
    )
    created_at = fields.DatetimeField()
    items_count = fields.IntField(default=0)
    cover: fields.ForeignKeyRelation[MediaItem] | None = fields.ForeignKeyField(
        "models.MediaItem", related_name="album_covers", on_delete=fields.SET_NULL,
        null=True,
    )
    items: fields.ManyToManyRelation[MediaItem] = fields.ManyToManyField(
        "models.MediaItem",
        related_name="albums",
        through="album_items",
        on_delete=fields.SET_NULL,
    )

    class Meta:
        unique_together = (("owner", "slug"),)


class AlbumItems(models.Model):
    """Through table for Album-MediaItem M2M."""
    id = fields.UUIDField(primary_key=True, default=uuid7)
    album: fields.ForeignKeyRelation[Album] = fields.ForeignKeyField(
        "models.Album", related_name="item_links", on_delete=fields.CASCADE,
    )
    media_item: fields.ForeignKeyRelation[MediaItem] = fields.ForeignKeyField(
        "models.MediaItem", related_name="album_links", on_delete=fields.CASCADE,
    )


class AuditTrail(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    created_at = fields.DatetimeField()
    action: fields.ForeignKeyRelation[AuditTrailAction] = fields.ForeignKeyField(
        "models.AuditTrailAction",
        related_name="audit_trails",
        on_delete=fields.CASCADE,
    )
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="audit_trails", on_delete=fields.CASCADE,
    )


class AuditTrailAsset(models.Model):
    """Through table for AuditTrail-File M2M."""
    id = fields.IntField(primary_key=True)
    audit_trail: fields.ForeignKeyRelation[AuditTrail] = fields.ForeignKeyField(
        "models.AuditTrail", related_name="assets", on_delete=fields.CASCADE,
    )
    file: fields.ForeignKeyRelation[File] = fields.ForeignKeyField(
        "models.File", related_name="audit_trail_assets", on_delete=fields.CASCADE,
    )


class Blob(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    storage_key = fields.CharField(max_length=4096, unique=True)
    size = fields.BigIntField()
    chash = fields.CharField(max_length=128, index=True)
    media_type = fields.CharField(max_length=255)
    created_at = fields.DatetimeField()


class BlobMetadata(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    data = fields.JSONField()  # type: ignore[var-annotated]
    blob: fields.ForeignKeyRelation[Blob] = fields.OneToOneField(
        "models.Blob", related_name="metadata", on_delete=fields.CASCADE,
    )


class Bookmark(models.Model):
    """Through model for User-File bookmarks."""
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="bookmarks", on_delete=fields.CASCADE,
    )
    file: fields.ForeignKeyRelation[File] = fields.ForeignKeyField(
        "models.File", related_name="bookmarked_by", on_delete=fields.CASCADE,
    )

    class Meta:
        unique_together = (("user", "file"),)


class File(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    name = fields.CharField(max_length=1024)
    path = fields.CharField(max_length=4096)
    chash = fields.CharField(max_length=128)
    size = fields.BigIntField()
    modified_at = fields.DatetimeField()
    mediatype: fields.ForeignKeyRelation[MediaType] = fields.ForeignKeyField(
        "models.MediaType", related_name="files", on_delete=fields.RESTRICT,
    )
    namespace: fields.ForeignKeyRelation[Namespace] = fields.ForeignKeyField(
        "models.Namespace", related_name="files", on_delete=fields.CASCADE,
    )
    deleted_at = fields.DatetimeField(null=True)
    categories: fields.ManyToManyRelation[FileCategory] = fields.ManyToManyField(
        "models.FileCategory",
        related_name="files",
        through="file_file_category",
    )

    class Meta:
        unique_together = (("path", "namespace"),)
        indexes = (("chash", "namespace"),)


class FileCategory(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    name = fields.CharField(max_length=255, unique=True)


class FileFileCategoryThrough(models.Model):
    """Through table for File-FileCategory M2M with extra fields."""
    id = fields.IntField(primary_key=True)
    file: fields.ForeignKeyRelation[File] = fields.ForeignKeyField(
        "models.File", related_name="category_links", on_delete=fields.CASCADE,
    )
    file_category: fields.ForeignKeyRelation[FileCategory] = fields.ForeignKeyField(
        "models.FileCategory", related_name="file_links", on_delete=fields.CASCADE,
    )
    origin = fields.SmallIntField(null=True)
    probability = fields.SmallIntField(null=True)


class FileMember(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    actions = fields.SmallIntField()
    created_at = fields.DatetimeField()
    file: fields.ForeignKeyRelation[File] = fields.ForeignKeyField(
        "models.File", related_name="members", on_delete=fields.CASCADE,
    )
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="file_memberships", on_delete=fields.CASCADE,
    )

    class Meta:
        unique_together = (("file", "user"),)


class FileMemberMountPoint(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    display_name = fields.CharField(max_length=1024)
    member: fields.ForeignKeyRelation[FileMember] = fields.OneToOneField(
        "models.FileMember", related_name="mount_point", on_delete=fields.CASCADE,
    )
    parent: fields.ForeignKeyRelation[File] = fields.ForeignKeyField(
        "models.File", related_name="mount_points", on_delete=fields.CASCADE,
    )


class FileMetadata(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    data = fields.JSONField()  # type: ignore[var-annotated]
    file: fields.ForeignKeyRelation[File] = fields.OneToOneField(
        "models.File", related_name="metadata", on_delete=fields.CASCADE,
    )


class FilePendingDeletion(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    storage_key = fields.CharField(max_length=4096)
    chash = fields.CharField(max_length=128)
    mediatype = fields.CharField(max_length=255)
    created_at = fields.DatetimeField()



class Fingerprint(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    part1 = fields.IntField()
    part2 = fields.IntField()
    part3 = fields.IntField()
    part4 = fields.IntField()
    file: fields.ForeignKeyRelation[File] = fields.OneToOneField(
        "models.File", related_name="fingerprint", on_delete=fields.CASCADE,
    )

    class Meta:
        indexes = (("part1",), ("part2",), ("part3",), ("part4",))


class MediaItem(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    owner: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="media_items", on_delete=fields.CASCADE,
    )
    blob: fields.ForeignKeyRelation[Blob] = fields.ForeignKeyField(
        "models.Blob", related_name="media_items", on_delete=fields.RESTRICT,
    )
    name = fields.CharField(max_length=1024)
    created_at = fields.DatetimeField()
    modified_at = fields.DatetimeField()
    deleted_at = fields.DatetimeField(null=True)
    categories: fields.ManyToManyRelation[FileCategory] = fields.ManyToManyField(
        "models.FileCategory",
        through="media_item_category",
        related_name="media_items",
    )


class MediaItemBookmark(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="media_item_bookmarks", on_delete=fields.CASCADE,
    )
    media_item: fields.ForeignKeyRelation[MediaItem] = fields.ForeignKeyField(
        "models.MediaItem", related_name="bookmarks", on_delete=fields.CASCADE,
    )

    class Meta:
        unique_together = (("user", "media_item"),)


class MediaItemCategoryThrough(models.Model):
    id = fields.IntField(primary_key=True)
    media_item: fields.ForeignKeyRelation[MediaItem] = fields.ForeignKeyField(
        "models.MediaItem", on_delete=fields.CASCADE,
    )
    file_category: fields.ForeignKeyRelation[FileCategory] = fields.ForeignKeyField(
        "models.FileCategory", on_delete=fields.CASCADE,
    )
    origin = fields.SmallIntField(null=True)
    probability = fields.SmallIntField(null=True)

    class Meta:
        unique_together = (("media_item", "file_category"),)


class MediaType(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    name = fields.CharField(max_length=255, unique=True)


class Namespace(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    path = fields.CharField(max_length=1024, unique=True)
    owner: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="namespaces", on_delete=fields.CASCADE,
    )


class SharedLink(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    token = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField()
    file: fields.ForeignKeyRelation[File] = fields.OneToOneField(
        "models.File", related_name="shared_link", on_delete=fields.CASCADE,
    )


class User(models.Model):
    id = fields.UUIDField(primary_key=True, default=uuid7)
    username = fields.CharField(max_length=255, unique=True)
    password = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, unique=True, null=True)
    email_verified = fields.BooleanField(default=False)
    display_name = fields.CharField(max_length=255)
    created_at = fields.DatetimeField()
    last_login_at = fields.DatetimeField(null=True)
    active = fields.BooleanField(default=True)
    superuser = fields.BooleanField(default=False)
