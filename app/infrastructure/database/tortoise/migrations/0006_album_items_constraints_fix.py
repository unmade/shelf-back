from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0005_auto_20260424_1947")]

    initial = False

    operations = [
        ops.RunSQL(
            sql=[
                (
                    "ALTER TABLE album_items "
                    "DROP CONSTRAINT IF EXISTS album_items_album_id_fkey"
                ),
                (
                    "ALTER TABLE album_items "
                    "DROP CONSTRAINT IF EXISTS album_items_file_id_fkey"
                ),
                (
                    "ALTER TABLE album_items "
                    "DROP CONSTRAINT IF EXISTS album_items_mediaitem_id_fkey"
                ),
                (
                    "ALTER TABLE album_items "
                    "ADD CONSTRAINT album_items_album_id_fkey "
                    "FOREIGN KEY (album_id) REFERENCES album(id) ON DELETE CASCADE"
                ),
                (
                    "ALTER TABLE album_items "
                    "ADD CONSTRAINT album_items_mediaitem_id_fkey "
                    "FOREIGN KEY (mediaitem_id) REFERENCES mediaitem(id) "
                    "ON DELETE CASCADE"
                ),
            ],
            reverse_sql=[
                (
                    "ALTER TABLE album_items "
                    "DROP CONSTRAINT IF EXISTS album_items_album_id_fkey"
                ),
                (
                    "ALTER TABLE album_items "
                    "DROP CONSTRAINT IF EXISTS album_items_mediaitem_id_fkey"
                ),
                (
                    "ALTER TABLE album_items "
                    "DROP CONSTRAINT IF EXISTS album_items_file_id_fkey"
                ),
                (
                    "ALTER TABLE album_items "
                    "ADD CONSTRAINT album_items_album_id_fkey "
                    "FOREIGN KEY (album_id) REFERENCES album(id) ON DELETE SET NULL"
                ),
                (
                    "ALTER TABLE album_items "
                    "ADD CONSTRAINT album_items_file_id_fkey "
                    "FOREIGN KEY (mediaitem_id) REFERENCES file(id) ON DELETE SET NULL"
                ),
            ],
        ),
    ]
