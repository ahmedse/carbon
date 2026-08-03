# File: importexport/services.py
# Service layer for the importexport app (Facade pattern).
# Views call these services; services return plain data (model instances/dicts),
# never DRF Response objects.

import csv
import io
import logging

from django.core.files.base import ContentFile
from django.utils import timezone

from dataschema.models import DataTable, DataRow
from dataschema.services import BulkImportService
from .models import ImportJob, ExportJob

logger = logging.getLogger(__name__)


class ImportService:
    """Import job creation and execution."""

    @staticmethod
    def run_import(data_table_id, file, format_type='excel', source_id=None, user=None):
        """
        Create a pending ImportJob and execute the import synchronously.

        ADR: Synchronous execution (no Celery). For large files (>10k rows)
        this may block the request; migrate to async task queue if needed.

        Returns the ImportJob instance with final status.
        """
        job = ImportJob.objects.create(
            data_table_id=data_table_id,
            source_id=source_id or None,
            file=file,
            format=format_type,
            user=user,
            status='pending',
        )

        try:
            job.status = 'running'
            job.started_at = timezone.now()
            job.save(update_fields=['status', 'started_at'])

            data_table = DataTable.objects.get(id=data_table_id)

            # Re-open the saved file for reading by BulkImportService
            job.file.open('rb')
            try:
                result = BulkImportService.import_rows(
                    data_table, job.file, created_by=user
                )
            finally:
                job.file.close()

            job.row_count = result['created']
            job.error_count = result['failed']
            job.log = result['errors']
            job.status = 'done'
            job.finished_at = timezone.now()
            job.save()

        except Exception as exc:
            logger.exception('Import job %s failed', job.id)
            job.status = 'failed'
            job.error_count = (job.error_count or 0) + 1
            if not job.log:
                job.log = []
            job.log.append({'error': str(exc)})
            job.finished_at = timezone.now()
            job.save(update_fields=['status', 'error_count', 'log', 'finished_at'])

        return job


class ExportService:
    """Export job creation, execution, and download resolution."""

    @staticmethod
    def run_export(project, user=None):
        """
        Create a pending ExportJob from an export project and execute synchronously.

        ADR: Synchronous execution (no Celery). Scheduled exports are not
        implemented; the ExportProject.schedule field is hidden from the API.

        Returns the ExportJob instance with final status.
        """
        job = ExportJob.objects.create(
            export_project=project,
            data_table=project.data_table,
            format=project.format,
            filters=project.filters,
            user=user,
            status='pending',
        )

        try:
            job.status = 'running'
            job.started_at = timezone.now()
            job.save(update_fields=['status', 'started_at'])

            # Query rows for the table
            rows = DataRow.objects.filter(
                data_table=project.data_table, is_archived=False
            )

            # Apply JSON field filters
            if project.filters:
                for field_name, field_value in project.filters.items():
                    lookup = f'values__{field_name}'
                    rows = rows.filter(**{lookup: field_value})

            # Determine columns from active table fields
            fields = project.data_table.fields.filter(
                is_active=True, is_archived=False
            ).order_by('order')
            headers = [f.name for f in fields]

            # Generate CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            row_count = 0
            for row in rows:
                writer.writerow(row.values)
                row_count += 1

            csv_bytes = output.getvalue().encode('utf-8')

            # Save file to media/exports/
            filename = (
                f"{project.slug}_"
                f"{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            job.file.save(filename, ContentFile(csv_bytes))
            job.row_count = row_count
            job.status = 'ready'
            job.finished_at = timezone.now()
            job.save()

        except Exception as exc:
            logger.exception('Export job %s failed', job.id)
            job.status = 'failed'
            job.finished_at = timezone.now()
            job.save(update_fields=['status', 'finished_at'])

        return job

    @staticmethod
    def get_download(job):
        """
        Resolve the download for an export job.
        Returns {'download_url': ...} when ready, otherwise an error dict with
        'error' and 'status_code' for the view to translate into a Response.
        """
        if job.status != 'ready':
            return {
                'error': f'Export not ready (status: {job.status})',
                'status_code': 400,
            }
        if not job.file:
            return {'error': 'No file available', 'status_code': 404}
        return {'download_url': job.file.url}
