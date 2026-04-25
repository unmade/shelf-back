from uuid import uuid7

from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0004_blob_metadata")]

    initial = False

    operations = [
        ops.RenameModel(old_name="FileCategory", new_name="MediaItemCategory"),
        ops.CreateModel(
            name="MediaItem",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                (
                    "owner",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="owner_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="media_items",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "blob",
                    fields.ForeignKeyField(
                        "models.Blob",
                        source_field="blob_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="media_items",
                        on_delete=OnDelete.RESTRICT,
                    ),
                ),
                ("name", fields.CharField(max_length=1024)),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
                (
                    "modified_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
                (
                    "deleted_at",
                    fields.DatetimeField(null=True, auto_now=False, auto_now_add=False),
                ),
            ],
            options={"table": "mediaitem", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="MediaItemFavourite",
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
                        related_name="media_item_favourites",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "media_item",
                    fields.ForeignKeyField(
                        "models.MediaItem",
                        source_field="media_item_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="favourited_by",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={
                "table": "mediaitemfavourite",
                "app": "models",
                "unique_together": (("user", "media_item"),),
                "pk_attr": "id",
            },
            bases=["Model"],
        ),
        ops.CreateModel(
            name="MediaItemCategoryThrough",
            fields=[
                (
                    "id",
                    fields.IntField(
                        generated=True, primary_key=True, unique=True, db_index=True
                    ),
                ),
                (
                    "media_item",
                    fields.ForeignKeyField(
                        "models.MediaItem",
                        source_field="media_item_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="category_links",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                (
                    "media_item_category",
                    fields.ForeignKeyField(
                        "models.MediaItemCategory",
                        source_field="media_item_category_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="media_item_links",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("origin", fields.SmallIntField(null=True)),
                ("probability", fields.SmallIntField(null=True)),
            ],
            options={
                "table": "mediaitemcategorythrough",
                "app": "models",
                "unique_together": (("media_item", "media_item_category"),),
                "pk_attr": "id",
            },
            bases=["Model"],
        ),
        ops.AlterField(
            model_name="Album",
            name="items",
            field=fields.ManyToManyField(
                "models.MediaItem",
                unique=True,
                db_constraint=True,
                through="album_items",
                forward_key="mediaitem_id",
                backward_key="album_id",
                related_name="albums",
                on_delete=OnDelete.CASCADE,
            ),
        ),
        ops.RemoveField(model_name="File", name="categories"),
        ops.DeleteModel(name="AlbumItems"),
        ops.DeleteModel(name="FileFileCategoryThrough"),
    ]
