from uuid import uuid7

from orjson import loads
from tortoise import fields, migrations
from tortoise.fields.data import JSON_DUMPS
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0007_auto_20260428_2313")]

    initial = False

    operations = [
        ops.CreateModel(
            name="BlobJob",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("type", fields.CharField(max_length=255)),
                ("data", fields.JSONField(encoder=JSON_DUMPS, decoder=loads)),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
            ],
            options={"table": "blobjob", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.DeleteModel(name="FilePendingDeletion"),
    ]
