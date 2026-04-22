from uuid import uuid7

from tortoise import fields, migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0002_file_pending_deletion_storage_key")]

    initial = False

    operations = [
        ops.CreateModel(
            name="Blob",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid7, unique=True, db_index=True
                    ),
                ),
                ("storage_key", fields.CharField(unique=True, max_length=4096)),
                ("size", fields.BigIntField()),
                ("chash", fields.CharField(db_index=True, max_length=128)),
                ("media_type", fields.CharField(max_length=255)),
                (
                    "created_at",
                    fields.DatetimeField(auto_now=False, auto_now_add=False),
                ),
            ],
            options={"table": "blob", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
    ]
