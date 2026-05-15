from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0015_auto_20260515_1618")]

    initial = False

    operations = [
        ops.DeleteModel(name="FileMember"),
        ops.DeleteModel(name="FileMemberMountPoint"),
    ]
