from uuid import uuid7

from orjson import loads
from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.fields.data import JSON_DUMPS
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0003_blob")]

    initial = False

    operations = [
        ops.CreateModel(
            name="BlobMetadata",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("data", fields.JSONField(encoder=JSON_DUMPS, decoder=loads)),
                (
                    "blob",
                    fields.OneToOneField(
                        "models.Blob",
                        source_field="blob_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="metadata",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
            ],
            options={"table": "blobmetadata", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
    ]
