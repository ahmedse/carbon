from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0003_alter_governancepolicy_options_and_more'),
    ]
    
    operations = [
        migrations.AddIndex(
            model_name='assetprofile',
            index=models.Index(fields=['is_active', 'domain'], name='assetprof_active_domain_idx'),
        ),
        migrations.AddIndex(
            model_name='assetprofile',
            index=models.Index(fields=['quality_status'], name='assetprof_quality_idx'),
        ),
        migrations.AddIndex(
            model_name='governanceevent',
            index=models.Index(fields=['-timestamp', 'entity_type'], name='govevent_time_type_idx'),
        ),
    ]
