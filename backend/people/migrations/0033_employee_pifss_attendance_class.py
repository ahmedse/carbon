from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0032_compliancerule_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="pifss_registered",
            field=models.BooleanField(
                blank=True,
                default=None,
                help_text="Social-insurance registration. Null means unknown and indemnity that requires it refuses.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="absence_class",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Attendance classification supplied by the People plane. Blank means unclassified.",
                max_length=32,
            ),
        ),
    ]
