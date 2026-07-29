# File: backend/evidence/models.py
import os
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from dataschema.models import DataRow


User = get_user_model()


def evidence_upload_path(instance, filename):
    """Upload evidence files to media/evidence/YYYY/MM/DD/ directory."""
    today = timezone.now()
    return f'evidence/{today.year}/{today.month:02d}/{today.day:02d}/{filename}'


class Evidence(models.Model):
    """Evidence attachment for a data row (invoice, receipt, photo, etc.)"""
    
    data_row = models.ForeignKey(
        DataRow,
        on_delete=models.CASCADE,
        related_name='evidence',
        help_text='The data row this evidence is attached to'
    )
    
    file = models.FileField(
        upload_to=evidence_upload_path,
        help_text='Evidence file (PDF, image, Excel, etc.)'
    )
    
    original_filename = models.CharField(
        max_length=255,
        help_text='Original filename as uploaded by user'
    )
    
    file_size = models.BigIntegerField(
        help_text='File size in bytes'
    )
    
    mime_type = models.CharField(
        max_length=100,
        default='application/octet-stream',
        help_text='MIME type of the file'
    )
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_evidence',
        help_text='User who uploaded this evidence'
    )
    
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when file was uploaded'
    )
    
    is_deleted = models.BooleanField(
        default=False,
        help_text='Soft delete flag (preserve audit trail)'
    )
    
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when file was deleted (soft delete)'
    )
    
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_evidence',
        help_text='User who deleted this evidence'
    )
    
    class Meta:
        app_label = 'evidence'
        ordering = ['-uploaded_at']
        verbose_name = 'Evidence'
        verbose_name_plural = 'Evidence'
        indexes = [
            models.Index(fields=['data_row', '-uploaded_at']),
            models.Index(fields=['is_deleted']),
            models.Index(fields=['uploaded_by']),
        ]
    
    def __str__(self):
        return f"{self.original_filename} (Row {self.data_row.id})"
    
    def delete(self, *args, **kwargs):
        """Soft delete: mark as deleted rather than removing from DB."""
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        # Don't set deleted_by here - should be done by view with request.user
        self.save()
