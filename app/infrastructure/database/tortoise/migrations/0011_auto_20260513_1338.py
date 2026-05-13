from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0010_auto_20260512_1606")]

    initial = False

    operations = [
        ops.RemoveField(model_name="File", name="chash"),
        ops.RemoveField(model_name="File", name="mediatype"),
        ops.DeleteModel(name="MediaType"),
    ]
