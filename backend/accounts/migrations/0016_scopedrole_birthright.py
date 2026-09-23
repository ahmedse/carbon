from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_user_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='scopedrole',
            name='provenance',
            field=models.CharField(
                choices=[('birthright', 'Birthright'), ('exception', 'Exception')],
                default='exception',
                help_text='birthright is recalculated; exception is an explicit grant.',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='scopedrole',
            name='valid_from',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scopedrole',
            name='valid_to',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='DutyProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position_code', models.CharField(db_index=True, max_length=64)),
                ('duty', models.CharField(max_length=100)),
                ('scope', models.CharField(
                    choices=[
                        ('home_org', 'Home org unit'),
                        ('managed_org', 'Org units this person runs'),
                        ('global', 'Global'),
                    ],
                    default='home_org',
                    max_length=16,
                )),
            ],
            options={
                'verbose_name': 'Duty profile',
                'verbose_name_plural': 'Duty profiles',
                'unique_together': {('position_code', 'duty', 'scope')},
            },
        ),
    ]
