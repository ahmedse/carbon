# File: backend/evidence/views.py
import mimetypes
from django.http import FileResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Evidence
from .serializers import EvidenceSerializer, EvidenceUploadSerializer
from .permissions import IsEvidenceOwnerOrAdmin
from .services import EvidenceService
from dataschema.models import DataRow


class EvidenceViewSet(viewsets.ModelViewSet):
    """ViewSet for evidence attachments."""
    
    serializer_class = EvidenceSerializer
    permission_classes = [IsAuthenticated, IsEvidenceOwnerOrAdmin]
    # CBAC: declared for DoD visibility; the actual write gate is the
    # owner/module check in IsEvidenceOwnerOrAdmin (layer-2), which ORs
    # the evidence:manage capability (layer-1) with the owner check.
    required_write_capability = 'evidence:manage'
    filterset_fields = ['data_row', 'is_deleted', 'uploaded_by']
    search_fields = ['original_filename']
    ordering = ['-uploaded_at']
    
    def get_queryset(self):
        """Return evidence accessible by the current user."""
        if getattr(self, 'swagger_fake_view', False):
            return Evidence.objects.none()
        from accounts.rbac_utils import get_allowed_module_ids, user_is_global_admin
        
        user = self.request.user
        
        # Admins see all evidence
        if user_is_global_admin(user):
            return Evidence.objects.all().exclude(is_deleted=True)
        
        # Regular users see evidence only from their modules
        allowed_modules = get_allowed_module_ids(user, roles=['dataowners_group', 'auditors_group', 'admins_group'])
        return Evidence.objects.filter(
            data_row__data_table__module_id__in=allowed_modules
        ).exclude(is_deleted=True)
    
    def perform_create(self, serializer):
        """Set uploaded_by to current user."""
        serializer.save(uploaded_by=self.request.user)
    
    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """Download an evidence file."""
        evidence = self.get_object()
        
        file_obj = evidence.file
        if not file_obj:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Determine MIME type from filename extension first, then fallback to stored mime_type
        mime_type = mimetypes.guess_type(evidence.file.name)[0]
        if not mime_type:
            mime_type = evidence.mime_type or 'application/octet-stream'

        # Return file with appropriate headers
        try:
            response = FileResponse(
                file_obj.open('rb'),
                content_type=mime_type
            )
        except FileNotFoundError:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        response['Content-Disposition'] = f'attachment; filename="{evidence.original_filename}"'
        return response
    
    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """Upload multiple evidence files for a data row."""
        serializer = EvidenceUploadSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data_row = serializer.validated_data['data_row']
        files = serializer.validated_data['files']

        results = EvidenceService.bulk_store(files, {
            'data_row': data_row,
            'uploaded_by': request.user,
        })

        return Response(results, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete: mark evidence as deleted."""
        instance = self.get_object()
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = request.user
        instance.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
