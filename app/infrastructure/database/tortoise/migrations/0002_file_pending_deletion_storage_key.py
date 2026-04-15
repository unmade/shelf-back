from tortoise import fields, migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0001_initial")]

    operations = [
        ops.AddField(
            model_name="FilePendingDeletion",
            name="storage_key",
            field=fields.CharField(max_length=4096, default=""),
        ),
        ops.RunSQL(
            sql=("UPDATE filependingdeletion SET storage_key = ns_path || '/' || path"),
        ),
        ops.RemoveField(
            model_name="FilePendingDeletion",
            name="ns_path",
        ),
        ops.RemoveField(
            model_name="FilePendingDeletion",
            name="path",
        ),
    ]
