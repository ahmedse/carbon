from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inbound', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InboundCartridge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=80, unique=True)),
                ('kind', models.CharField(choices=[('typed_object', 'Typed object'), ('data_product', 'Data product')], max_length=20)),
                ('label', models.CharField(max_length=160)),
                ('label_ar', models.CharField(blank=True, default='', max_length=160)),
                ('owner_app', models.CharField(max_length=40)),
                ('fields', models.JSONField(blank=True, default=list)),
                ('enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['key'],
            },
        ),
    ]
