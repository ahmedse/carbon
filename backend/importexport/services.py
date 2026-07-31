# File: importexport/services.py
# Service layer for the importexport app (Facade pattern).
# Views call these services; services return plain data (model instances/dicts),
# never DRF Response objects. Zero behavioral change vs. the logic previously in views.

from .models import ImportJob, ExportJob


class ImportService:
    """Import job creation."""

    @staticmethod
    def run_import(data_table_id, file, format_type='excel', source_id=None, user=None):
        """
        Create a pending ImportJob. Returns the ImportJob instance.
        (Extracted from ImportJobViewSet.create — the view validates the
        required params, the service builds the job.)
        """
        return ImportJob.objects.create(
            data_table_id=data_table_id,
            source_id=source_id or None,
            file=file,
            format=format_type,
            user=user,
            status='pending',
        )


class ExportService:
    """Export job creation and download resolution."""

    @staticmethod
    def run_export(project, user=None):
        """
        Create a pending ExportJob from an export project. Returns the ExportJob
        instance. (Extracted from ExportProjectViewSet.run.)
        """
        return ExportJob.objects.create(
            export_project=project,
            data_table=project.data_table,
            format=project.format,
            filters=project.filters,
            user=user,
            status='pending',
        )

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
