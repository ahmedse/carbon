import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('excellence', '0002_run'),
    ]

    operations = [
        migrations.CreateModel(
            name='Initiative',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=160)),
                ('tier', models.CharField(db_index=True, max_length=40)),
                ('target_level', models.PositiveSmallIntegerField()),
                ('app_ids', models.JSONField(blank=True, default=list)),
                ('deadline', models.DateField(db_index=True)),
                ('owner', models.CharField(max_length=120)),
                ('status', models.CharField(default='open', max_length=12)),
                ('note', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'ordering': ['deadline', '-id'],
            },
        ),
    ]
