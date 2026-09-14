# Generated manually for P3-06 (mirrors ``makemigrations ai`` output).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0031_approvalgrant'),
    ]

    operations = [
        migrations.AddField(
            model_name='policydecisionrow',
            name='stage',
            field=models.TextField(db_index=True, default='pdp'),
        ),
    ]
