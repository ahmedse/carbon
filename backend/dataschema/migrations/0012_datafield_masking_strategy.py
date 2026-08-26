# Generated migration for DataField.masking_strategy (EPH-4B: Data Masking Engine)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataschema', '0011_fieldaccesspolicy'),
    ]

    operations = [
        migrations.AddField(
            model_name='datafield',
            name='masking_strategy',
            field=models.CharField(choices=[('none', 'None'), ('redact', '[REDACTED]'), ('hash', 'Hash (SHA-256 12-char)'), ('truncate', 'Truncate (3 chars + ***)'), ('null', 'Null (empty)')], default='none', max_length=20),
        ),
    ]
