from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dataschema', '0009_datatable_search_vector_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='datatable',
            name='last_data_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
