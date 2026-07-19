# Generated migration for TableRelation model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dataschema', '0002_datafield_reference_set'),
    ]

    operations = [
        migrations.CreateModel(
            name='TableRelation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('relation_type', models.CharField(choices=[('one_to_many', 'One → Many'), ('many_to_many', 'Many → Many'), ('lookup', 'Lookup')], default='one_to_many', max_length=20)),
                ('label', models.CharField(blank=True, max_length=120)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_relations', to=settings.AUTH_USER_MODEL)),
                ('from_field', models.ForeignKey(blank=True, help_text='The FK column on from_table (optional)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outgoing_relations', to='dataschema.datafield')),
                ('from_table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_relations', to='dataschema.datatable')),
                ('to_field', models.ForeignKey(blank=True, help_text='The PK/target column on to_table (optional)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incoming_relations', to='dataschema.datafield')),
                ('to_table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incoming_relations', to='dataschema.datatable')),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('from_table', 'to_table', 'from_field', 'to_field')},
            },
        ),
    ]
