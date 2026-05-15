from tortoise import migrations
from tortoise.migrations import operations as ops


async def backfill_file_owner(apps, _schema_editor) -> None:
    FileModel = apps.get_model("models.File")

    while True:
        files = await (
            FileModel.filter(owner_id__isnull=True)
            .select_related("namespace")
            .limit(1000)
        )
        if not files:
            return

        for file in files:
            file.owner_id = file.namespace.owner_id

        await FileModel.bulk_update(files, fields=["owner_id"])


class Migration(migrations.Migration):
    dependencies = [("models", "0012_auto_20260515_1302")]

    initial = False

    operations = [
        ops.RunPython(
            backfill_file_owner,
            reverse_code=ops.RunPython.noop,
        ),
    ]
