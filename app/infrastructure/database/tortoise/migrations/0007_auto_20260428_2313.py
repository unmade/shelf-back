from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0006_album_items_constraints_fix")]

    initial = False

    operations = [
        ops.AddField(
            model_name="File",
            name="blob",
            field=fields.ForeignKeyField(
                "models.Blob",
                source_field="blob_id",
                null=True,
                db_constraint=True,
                to_field="id",
                related_name="files",
                on_delete=OnDelete.RESTRICT,
            ),
        ),
    ]
