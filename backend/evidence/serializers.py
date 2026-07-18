# File: backend/evidence/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Evidence
from dataschema.models import DataRow


User = get_user_model()


class EvidenceSerializer(serializers.ModelSerializer):
    """Serializer for evidence attachments with metadata."""
    
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    deleted_by_name = serializers.CharField(source='deleted_by.get_full_name', read_only=True, allow_null=True)
    deleted_by_username = serializers.CharField(source='deleted_by.username', read_only=True, allow_null=True)
    download_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Evidence
        fields = [
            'id',
            'data_row',
            'original_filename',
            'file_size',
            'mime_type',
            'uploaded_by',
            'uploaded_by_name',
            'uploaded_by_username',
            'uploaded_at',
            'is_deleted',
            'deleted_at',
            'deleted_by',
            'deleted_by_name',
            'deleted_by_username',
            'download_url',
        ]
        read_only_fields = [
            'id',
            'file_size',
            'mime_type',
            'uploaded_by',
            'uploaded_at',
            'deleted_at',
            'deleted_by',
            'download_url',
        ]
    
    def get_download_url(self, obj):
        """Generate download URL for the evidence file."""
        if obj.id:
            return f'/carbon-api/evidence/{obj.id}/download/'
        return None


class EvidenceUploadSerializer(serializers.Serializer):
    """Serializer for bulk file upload endpoint."""
    
    data_row = serializers.PrimaryKeyRelatedField(queryset=DataRow.objects.all())
    files = serializers.ListField(child=serializers.FileField())
    
    def validate_files(self, files):
        """Validate file types and sizes."""
        ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'csv', 'docx', 'txt', 'zip', 'xls'}
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        
        errors = []
        for file in files:
            # Check extension
            ext = file.name.split('.')[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors.append(f"{file.name}: File type .{ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
            
            # Check size
            if file.size > MAX_FILE_SIZE:
                size_mb = file.size / (1024 * 1024)
                errors.append(f"{file.name}: File size {size_mb:.1f}MB exceeds 50MB limit")
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return files
    
    def create(self, validated_data):
        """This is handled by the viewset action, not the serializer."""
        pass
