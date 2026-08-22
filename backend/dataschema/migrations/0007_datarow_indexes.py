from django.db import migrations, models


class Migration(migrations.Migration):
    # CONCURRENTLY cannot run inside a transaction
    atomic = False

    dependencies = [
        ('dataschema', '0006_datarow_append_only'),
    ]

    operations = [
        # SeparateDatabaseAndState: DDL uses CONCURRENTLY; state ops update Django's index registry.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS datarow_table_id_idx "
                        "ON dataschema_datarow (data_table_id, id);"
                    ),
                    reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS datarow_table_id_idx;",
                ),
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS datarow_table_time_idx "
                        "ON dataschema_datarow (data_table_id, created_at);"
                    ),
                    reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS datarow_table_time_idx;",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE dataschema_datarow SET (fillfactor = 100);",
                    reverse_sql="ALTER TABLE dataschema_datarow RESET (fillfactor);",
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name='datarow',
                    index=models.Index(fields=['data_table', 'id'], name='datarow_table_id_idx'),
                ),
                migrations.AddIndex(
                    model_name='datarow',
                    index=models.Index(fields=['data_table', 'created_at'], name='datarow_table_time_idx'),
                ),
            ],
        ),
    ]
