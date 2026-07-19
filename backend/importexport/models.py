# importexport/models.py — Import/export jobs for dataschema tables
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from dataschema.models import DataTable
from connections.models import DataSource

User = get_user_model()


class ExportProject(models.Model):
    """
    A named export project: reusable configuration for exporting table data.
    Can be run manually or on a schedule (schedule support is for future).
    """
    FORMATS = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ]
    SCHEDULES = [
        ('manual', 'Manual'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    data_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='export_projects'
    )
    format = models.CharField(max_length=20, choices=FORMATS, default='excel')
    filters = models.JSONField(default=dict, blank=True, help_text="Field-level filters, date range, etc.")
    schedule = models.CharField(max_length=20, choices=SCHEDULES, default='manual')
    is_active = models.BooleanField(default=True)
    owner = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_export_projects'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.data_table.title})"


class ImportJob(models.Model):
    """
    A bulk import job: file → DataTable, with validation log and error tracking.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    data_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='import_jobs'
    )
    source = models.ForeignKey(
        DataSource, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='import_jobs'
    )
    file = models.FileField(upload_to='imports/%Y/%m/')
    format = models.CharField(
        max_length=20, choices=[('csv', 'CSV'), ('excel', 'Excel')], default='excel'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    row_count = models.IntegerField(null=True, blank=True)
    error_count = models.IntegerField(null=True, blank=True)
    log = models.JSONField(default=list, blank=True, help_text="List of {row, error} objects")
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='import_jobs'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Import {self.id} to {self.data_table.title} ({self.status})"


class ExportJob(models.Model):
    """
    A specific export job: can be ad-hoc or triggered from an ExportProject.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    export_project = models.ForeignKey(
        ExportProject, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='jobs'
    )
    data_table = models.ForeignKey(
        DataTable, on_delete=models.CASCADE, related_name='export_jobs'
    )
    format = models.CharField(
        max_length=20, choices=[('csv', 'CSV'), ('excel', 'Excel'), ('json', 'JSON')]
    )
    filters = models.JSONField(default=dict, blank=True)
    file = models.FileField(null=True, blank=True, upload_to='exports/%Y/%m/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    row_count = models.IntegerField(null=True, blank=True)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='export_jobs'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Export {self.id} of {self.data_table.title} ({self.status})"
