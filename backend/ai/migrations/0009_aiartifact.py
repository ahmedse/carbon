from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0008_aiconversation_last_summarized_message_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AIArtifact",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "title",
                    models.CharField(max_length=255),
                ),
                (
                    "artifact_type",
                    models.CharField(
                        choices=[
                            ("report", "Report"),
                            ("rule_set", "Rule Set"),
                            ("query", "Query"),
                            ("analysis", "Analysis"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "content_json",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "visibility",
                    models.CharField(
                        choices=[("private", "Private"), ("shared", "Shared")],
                        default="private",
                        max_length=20,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artifacts",
                        to="ai.aiconversation",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_ai_artifacts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "message",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="artifacts",
                        to="ai.aimessage",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="aiartifact",
            index=models.Index(fields=["conversation", "visibility", "-created_at"], name="ai_art_conv_vis_idx"),
        ),
        migrations.AddIndex(
            model_name="aiartifact",
            index=models.Index(fields=["created_by", "visibility"], name="ai_art_creator_vis_idx"),
        ),
        migrations.AddIndex(
            model_name="aiartifact",
            index=models.Index(fields=["artifact_type", "visibility"], name="ai_art_type_vis_idx"),
        ),
    ]