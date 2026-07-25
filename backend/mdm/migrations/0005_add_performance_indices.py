from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('mdm', '0004_reference_set_lifecycle'),
    ]
    
    operations = [
        migrations.AddIndex(
            model_name='referenceset',
            index=models.Index(fields=['is_active', 'domain'], name='refset_active_domain_idx'),
        ),
        migrations.AddIndex(
            model_name='referencevalue',
            index=models.Index(fields=['reference_set', 'is_active'], name='refval_set_active_idx'),
        ),
        migrations.AddIndex(
            model_name='referencevalue',
            index=models.Index(fields=['valid_from', 'valid_to'], name='refval_validity_idx'),
        ),
    ]
