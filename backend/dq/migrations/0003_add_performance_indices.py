from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('dq', '0002_alter_dqrule_options_dqrule_created_by_dqrule_name_and_more'),
    ]
    
    operations = [
        migrations.AddIndex(
            model_name='dqresult',
            index=models.Index(fields=['-run_at', 'rule'], name='dqresult_time_rule_idx'),
        ),
        migrations.AddIndex(
            model_name='dqresult',
            index=models.Index(fields=['passed'], name='dqresult_passed_idx'),
        ),
    ]
