from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0014_auto_20260515_1303")]

    initial = False

    operations = [
        ops.DeleteModel(name="MediaItemCategoryThrough"),
        ops.DeleteModel(name="MediaItemCategory"),
    ]
