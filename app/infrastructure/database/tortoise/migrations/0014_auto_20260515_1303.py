from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0013_file_owner_backfill")]

    initial = False

    operations = [
        ops.AlterField(
            model_name="File",
            name="owner",
            field=fields.ForeignKeyField(
                "models.User",
                source_field="owner_id",
                db_constraint=True,
                to_field="id",
                related_name="files",
                on_delete=OnDelete.CASCADE,
            ),
        ),
    ]
