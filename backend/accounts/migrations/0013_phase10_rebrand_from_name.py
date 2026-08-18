# Generated manually for the rebrand (AASTMT · Data Trust Platform).
# Aligns EmailConfig.from_name default with the new platform identity.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_phase1_8_event_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailconfig',
            name='from_name',
            field=models.CharField(blank=True, default='AASTMT · Data Trust Platform', help_text='Display name for From: header', max_length=100),
        ),
    ]
