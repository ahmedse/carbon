# File: evidence/services.py
# Service layer for the evidence app (Facade pattern).
# Views call these services; services return plain data (dict/instances),
# never DRF Response objects. Zero behavioral change vs. the logic previously in views.

from .models import Evidence


class EvidenceService:
    """Evidence file persistence: single and bulk storage."""

    @staticmethod
    def store_evidence(file, metadata):
        """
        Persist a single evidence file.
        metadata: dict with keys 'data_row' (DataRow instance) and
        'uploaded_by' (request user). Returns the created Evidence instance.
        """
        mime_type = file.content_type or 'application/octet-stream'
        return Evidence.objects.create(
            data_row=metadata.get('data_row'),
            file=file,
            original_filename=file.name,
            file_size=file.size,
            mime_type=mime_type,
            uploaded_by=metadata.get('uploaded_by'),
        )

    @staticmethod
    def bulk_store(files, metadata):
        """
        Upload multiple evidence files for a data row.
        Returns per-file summary dict (results/total/success/failed) so partial
        failures do not abort the batch.
        """
        results = []
        success_count = 0

        for file in files:
            try:
                evidence = EvidenceService.store_evidence(file, metadata)
                results.append({
                    'id': evidence.id,
                    'filename': file.name,
                    'status': 'success',
                    'message': 'File uploaded successfully',
                })
                success_count += 1
            except Exception as e:
                results.append({
                    'filename': file.name,
                    'status': 'error',
                    'message': str(e),
                })

        return {
            'results': results,
            'total': len(files),
            'success': success_count,
            'failed': len(files) - success_count,
        }
