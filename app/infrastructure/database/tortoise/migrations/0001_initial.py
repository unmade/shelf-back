from uuid import uuid7

from orjson import loads
from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.fields.data import JSON_DUMPS
from tortoise.indexes import Index
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name="AuditTrailAction",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("name", fields.CharField(unique=True, max_length=255)),
            ],
            options={"table": "audittrailaction", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="FileCategory",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("name", fields.CharField(unique=True, max_length=255)),
            ],
            options={"table": "filecategory", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="FilePendingDeletion",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("ns_path", fields.CharField(max_length=1024)),
                ("path", fields.CharField(max_length=4096)),
                ("chash", fields.CharField(max_length=128)),
                ("mediatype", fields.CharField(max_length=255)),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
            ],
            options={"table": "filependingdeletion", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="MediaType",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("name", fields.CharField(unique=True, max_length=255)),
            ],
            options={"table": "mediatype", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("username", fields.CharField(unique=True, max_length=255)),
                ("password", fields.CharField(max_length=255)),
                ("email", fields.CharField(null=True, unique=True, max_length=255)),
                ("email_verified", fields.BooleanField(default=False)),
                ("display_name", fields.CharField(max_length=255)),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
                (
                    "last_login_at",
                    fields.DatetimeField(null=True, auto_now=False, auto_now_add=False),
                ),
                ("active", fields.BooleanField(default=True)),
                ("superuser", fields.BooleanField(default=False)),
            ],
            options={"table": "user", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Account",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                (
                    "user",
                    fields.OneToOneField(
                        "models.User",
                        source_field="user_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="account",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("storage_quota", fields.BigIntField(null=True)),
            ],
            options={"table": "account", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="AuditTrail",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
                (
                    "action",
                    fields.ForeignKeyField(
                        "models.AuditTrailAction",
                        source_field="action_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="audit_trails",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "user",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="user_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="audit_trails",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={"table": "audittrail", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Namespace",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("path", fields.CharField(unique=True, max_length=1024)),
                (
                    "owner",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="owner_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="namespaces",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={"table": "namespace", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="File",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("name", fields.CharField(max_length=1024)),
                ("path", fields.CharField(max_length=4096)),
                ("chash", fields.CharField(max_length=128)),
                ("size", fields.BigIntField()),
                (
                    "modified_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
                (
                    "mediatype",
                    fields.ForeignKeyField(
                        "models.MediaType",
                        source_field="mediatype_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="files",
                        on_delete=OnDelete.RESTRICT,
                    ),
                ),
                (
                    "namespace",
                    fields.ForeignKeyField(
                        "models.Namespace",
                        source_field="namespace_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="files",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "deleted_at",
                    fields.DatetimeField(null=True, auto_now=False, auto_now_add=False),
                ),
                (
                    "categories",
                    fields.ManyToManyField(
                        "models.FileCategory",
                        unique=True,
                        db_constraint=True,
                        through="file_file_category",
                        forward_key="filecategory_id",
                        backward_key="file_id",
                        related_name="files",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "file",
                "app": "models",
                "unique_together": (("path", "namespace"),),
                "indexes": [Index(fields=["chash", "namespace"])],
                "pk_attr": "id",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Album",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("title", fields.CharField(max_length=255)),
                ("slug", fields.CharField(max_length=255)),
                (
                    "owner",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="owner_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="albums",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
                ("items_count", fields.IntField(default=0)),
                (
                    "cover",
                    fields.ForeignKeyField(
                        "models.File",
                        source_field="cover_id",
                        null=True,
                        db_constraint=True,
                        to_field="id",
                        related_name="album_covers",
                        on_delete=OnDelete.SET_NULL,
                    ),
                ),
                (
                    "items",
                    fields.ManyToManyField(
                        "models.File",
                        unique=True,
                        db_constraint=True,
                        through="album_items",
                        forward_key="file_id",
                        backward_key="album_id",
                        related_name="albums",
                        on_delete=OnDelete.SET_NULL,
                    ),
                ),
            ],
            options={
                "table": "album",
                "app": "models",
                "unique_together": (("owner", "slug"),),
                "pk_attr": "id",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="AlbumItems",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                (
                    "album",
                    fields.ForeignKeyField(
                        "models.Album",
                        source_field="album_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="item_links",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "file",
                    fields.ForeignKeyField(
                        "models.File",
                        source_field="file_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="album_links",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "albumitems",
                "app": "models",
                "pk_attr": "id",
                "table_description": "Through table for Album-File M2M.",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="AuditTrailAsset",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                (
                    "audit_trail",
                    fields.ForeignKeyField(
                        "models.AuditTrail",
                        source_field="audit_trail_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="assets",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "file",
                    fields.ForeignKeyField(
                        "models.File",
                        source_field="file_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="audit_trail_assets",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "audittrailasset",
                "app": "models",
                "pk_attr": "id",
                "table_description": "Through table for AuditTrail-File M2M.",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Bookmark",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                (
                    "user",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="user_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="bookmarks",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "file",
                    fields.ForeignKeyField(
                        "models.File",
                        source_field="file_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="bookmarked_by",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "bookmark",
                "app": "models",
                "unique_together": (("user", "file"),),
                "pk_attr": "id",
                "table_description": "Through model for User-File bookmarks.",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="FileFileCategoryThrough",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                (
                    "file",
                    fields.ForeignKeyField(
                        "models.File",
                        source_field="file_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="category_links",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "file_category",
                    fields.ForeignKeyField(
                        "models.FileCategory",
                        source_field="file_category_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="file_links",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("origin", fields.SmallIntField(null=True)),
                ("probability", fields.SmallIntField(null=True)),
            ],
            options={
                "table": "filefilecategorythrough",
                "app": "models",
                "pk_attr": "id",
                "table_description": (
                    "Through table for File-FileCategory M2M with extra fields."
                ),
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="FileMember",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("actions", fields.SmallIntField()),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
                (
                    "file",
                    fields.ForeignKeyField(
                        "models.File",
                        source_field="file_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="members",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "user",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="user_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="file_memberships",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "filemember",
                "app": "models",
                "unique_together": (("file", "user"),),
                "pk_attr": "id",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="FileMemberMountPoint",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("display_name", fields.CharField(max_length=1024)),
                (
                    "member",
                    fields.OneToOneField(
                        "models.FileMember",
                        source_field="member_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="mount_point",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "parent",
                    fields.ForeignKeyField(
                        "models.File",
                        source_field="parent_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="mount_points",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={"table": "filemembermountpoint", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="FileMetadata",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("data", fields.JSONField(encoder=JSON_DUMPS, decoder=loads)),
                (
                    "file",
                    fields.OneToOneField(
                        "models.File",
                        source_field="file_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="metadata",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={"table": "filemetadata", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Fingerprint",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("part1", fields.IntField()),
                ("part2", fields.IntField()),
                ("part3", fields.IntField()),
                ("part4", fields.IntField()),
                (
                    "file",
                    fields.OneToOneField(
                        "models.File",
                        source_field="file_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="fingerprint",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "fingerprint",
                "app": "models",
                "indexes": [
                    Index(fields=["part1"]),
                    Index(fields=["part2"]),
                    Index(fields=["part3"]),
                    Index(fields=["part4"]),
                ],
                "pk_attr": "id",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="SharedLink",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("token", fields.CharField(unique=True, max_length=255)),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
                (
                    "file",
                    fields.OneToOneField(
                        "models.File",
                        source_field="file_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="shared_link",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={"table": "sharedlink", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
    ]
