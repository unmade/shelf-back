from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0011_auto_20260513_1338")]

    initial = False

    operations = [
        ops.AddField(
            model_name="File",
            name="owner",
            field=fields.ForeignKeyField(
                "models.User",
                source_field="owner_id",
                null=True,
                db_constraint=True,
                to_field="id",
                related_name="files",
                on_delete=OnDelete.CASCADE,
            ),
        ),
    ]
