# importexport/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

from .models import ExportProject, ImportJob, ExportJob
from .serializers import ExportProjectSerializer, ImportJobSerializer, ExportJobSerializer
from accounts.permissions import ReadAnyWriteGlobalAdmin


class ExportProjectViewSet(viewsets.ModelViewSet):
    """
    CRUD for export projects.
    Write/delete: global admin only.
    Read: any authenticated user.
    """
    queryset = ExportProject.objects.select_related('data_table', 'owner').order_by('-updated_at')
    serializer_class = ExportProjectSerializer
    permission_classes = [ReadAnyWriteGlobalAdmin]

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """
        POST /importexport/export-projects/{id}/run/
        Trigger a new ExportJob from this project.
        Response: { "job_id": <id>, "status": "pending" }
        """
        project = self.get_object()
        job = ExportJob.objects.create(
            export_project=project,
            data_table=project.data_table,
            format=project.format,
            filters=project.filters,
            user=request.user,
            status='pending',
        )
        return Response(
            ExportJobSerializer(job).data,
            status=status.HTTP_201_CREATED
        )


class ImportJobViewSet(viewsets.ModelViewSet):
    """
    Import job management: create, list, retrieve.
    Write: owner or global admin.
    Read: any authenticated user.
    """
    queryset = ImportJob.objects.select_related('data_table', 'source', 'user').order_by('-created_at')
    serializer_class = ImportJobSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get_permissions(self):
        if self.action == 'create':
            return [ReadAnyWriteGlobalAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """
        POST /importexport/import/
        Payload: { "data_table": <id>, "source": <id|null>, "file": <file>, "format": "excel"|"csv" }
        """
        data_table_id = request.data.get('data_table')
        file_obj = request.FILES.get('file')
        format_type = request.data.get('format', 'excel')

        if not data_table_id or not file_obj:
            return Response(
                {'error': 'data_table and file are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        job = ImportJob.objects.create(
            data_table_id=data_table_id,
            source_id=request.data.get('source') or None,
            file=file_obj,
            format=format_type,
            user=request.user,
            status='pending',
        )
        return Response(
            ImportJobSerializer(job).data,
            status=status.HTTP_201_CREATED
        )


class ExportJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Export job listing and retrieval (read-only; creation via ExportProjectViewSet.run()).
    """
    queryset = ExportJob.objects.select_related('data_table', 'export_project', 'user').order_by('-created_at')
    serializer_class = ExportJobSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        GET /importexport/export/{id}/download/
        Return the export file if ready.
        """
        job = self.get_object()
        if job.status != 'ready':
            return Response(
                {'error': f'Export not ready (status: {job.status})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not job.file:
            return Response(
                {'error': 'No file available'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response({'download_url': job.file.url})
