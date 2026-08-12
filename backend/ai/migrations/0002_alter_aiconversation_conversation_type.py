from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0001_add_workspace_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aiconversation",
            name="conversation_type",
            field=models.CharField(
                choices=[
                    ("chat", "Chat"),
                    ("dq_validate", "DQ Validate"),
                    ("dq_suggest", "DQ Suggest"),
                    ("nl_query", "NL Query"),
                    ("anomaly", "Anomaly"),
                ],
                default="chat",
                max_length=30,
            ),
        ),
    ]