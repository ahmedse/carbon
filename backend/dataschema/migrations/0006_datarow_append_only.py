from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dataschema', '0005_add_dq_flags'),
    ]

    operations = [
        migrations.RunSQL(
            sql="COMMENT ON TABLE dataschema_datarow IS "
                "'append-only trust layer — values column is immutable after insert';",
            reverse_sql="COMMENT ON TABLE dataschema_datarow IS NULL;",
        ),
    ]
