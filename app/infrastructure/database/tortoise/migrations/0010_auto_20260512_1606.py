from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0009_file_blob_backfill")]

    initial = False

    operations = [
        ops.DeleteModel(name="Fingerprint"),
    ]
