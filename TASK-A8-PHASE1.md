# TASK A8 - PHASE 1: Backend Evidence System

**Phase:** 1 of 5  
**Objective:** Create Django backend for evidence file attachments  
**Estimated Time:** 30-45 minutes

---

## What to Build

Create a Django app called `evidence` that allows users to upload evidence files (PDFs, images, documents) attached to data rows.

---

## Step-by-Step Instructions

### Step 1: Create Django App Structure (5 min)

```bash
cd backend
mkdir -p evidence
cd evidence
touch __init__.py apps.py models.py serializers.py views.py permissions.py urls.py admin.py
cd ..
```

### Step 2: Create apps.py

File: `backend/evidence/apps.py`

```python
from django.apps import AppConfig

class EvidenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'evidence'
```

### Step 3: Create Evidence Model

File: `backend/evidence/models.py`

```python
from django.db import models
from django.core.validators import FileExtensionValidator
from accounts.models import User
from dataschema.models import DataRow

class Evidence(models.Model):
    """Evidence file attached to a data row"""
    
    data_row = models.ForeignKey(DataRow, on_delete=models.CASCADE, related_name='evidence_files')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_evidence')
    
    file = models.FileField(
        upload_to='evidence/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'csv', 'docx', 'txt', 'zip'])]
    )
    
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    mime_type = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_evidence')
    
    class Meta:
        db_table = 'evidence'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['data_row', 'is_deleted']),
            models.Index(fields=['uploaded_by']),
        ]
    
    def __str__(self):
        return f"{self.original_filename} ({self.data_row.id})"
    
    @property
    def file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)
```

### Step 4: Create Serializers

File: `backend/evidence/serializers.py`

```python
from rest_framework import serializers
from .models import Evidence

class EvidenceSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size_mb = serializers.ReadOnlyField()
    
    class Meta:
        model = Evidence
        fields = ['id', 'data_row', 'file', 'original_filename', 'file_size', 'file_size_mb', 
                  'mime_type', 'description', 'uploaded_at', 'uploaded_by', 'uploaded_by_name', 
                  'file_url', 'is_deleted']
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by', 'file_size']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
    
    def create(self, validated_data):
        file = validated_data.get('file')
        validated_data['original_filename'] = file.name
        validated_data['file_size'] = file.size
        validated_data['mime_type'] = file.content_type or 'application/octet-stream'
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['uploaded_by'] = request.user
        
        return super().create(validated_data)
```

### Step 5: Create Permissions

File: `backend/evidence/permissions.py`

```python
from rest_framework import permissions

class EvidencePermission(permissions.BasePermission):
    """Users can access evidence from their modules. Admins can access all."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if user.is_superuser:
            return True
        
        data_row = obj.data_row
        module_id = data_row.data_table.module_id
        
        accessible_modules = user.context.get('modules', [])
        module_ids = [m['id'] for m in accessible_modules]
        
        return module_id in module_ids
```

### Step 6: Create ViewSet

File: `backend/evidence/views.py`

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse
from .models import Evidence
from .serializers import EvidenceSerializer
from .permissions import EvidencePermission

class EvidenceViewSet(viewsets.ModelViewSet):
    queryset = Evidence.objects.filter(is_deleted=False)
    serializer_class = EvidenceSerializer
    permission_classes = [EvidencePermission]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        
        data_row_id = self.request.query_params.get('data_row')
        if data_row_id:
            qs = qs.filter(data_row_id=data_row_id)
        
        if not user.is_superuser:
            accessible_modules = user.context.get('modules', [])
            module_ids = [m['id'] for m in accessible_modules]
            qs = qs.filter(data_row__data_table__module_id__in=module_ids)
        
        return qs
    
    def perform_destroy(self, instance):
        from django.utils import timezone
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save()
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        evidence = self.get_object()
        response = FileResponse(evidence.file.open('rb'), content_type=evidence.mime_type)
        response['Content-Disposition'] = f'attachment; filename="{evidence.original_filename}"'
        return response
    
    @action(detail=False, methods=['post'])
    def bulk_upload(self, request):
        files = request.FILES.getlist('files')
        data_row_id = request.data.get('data_row')
        
        if not data_row_id:
            return Response({'error': 'data_row is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        results = []
        for file in files:
            evidence_data = {'data_row': data_row_id, 'file': file}
            serializer = EvidenceSerializer(data=evidence_data, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                results.append({'filename': file.name, 'status': 'success', 'id': serializer.data['id']})
            else:
                results.append({'filename': file.name, 'status': 'error', 'errors': serializer.errors})
        
        return Response({
            'results': results,
            'total': len(files),
            'success': len([r for r in results if r['status'] == 'success'])
        })
```

### Step 7: Create URLs

File: `backend/evidence/urls.py`

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EvidenceViewSet

router = DefaultRouter()
router.register(r'evidence', EvidenceViewSet, basename='evidence')

urlpatterns = [
    path('', include(router.urls)),
]
```

### Step 8: Create Admin Interface

File: `backend/evidence/admin.py`

```python
from django.contrib import admin
from .models import Evidence

@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_filename', 'data_row', 'uploaded_by', 'file_size_mb', 'uploaded_at', 'is_deleted']
    list_filter = ['is_deleted', 'uploaded_at', 'mime_type']
    search_fields = ['original_filename', 'data_row__id', 'uploaded_by__username']
    readonly_fields = ['uploaded_at', 'file_size', 'mime_type']
    
    def file_size_mb(self, obj):
        return f"{obj.file_size_mb} MB"
    file_size_mb.short_description = 'File Size'
```

### Step 9: Update Settings

File: `backend/config/settings.py`

Add to INSTALLED_APPS:
```python
INSTALLED_APPS = [
    # ... existing apps ...
    'evidence',  # Add this line
]
```

Add at the end of the file:
```python
# Media files
import os
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
```

### Step 10: Update URLs

File: `backend/config/urls.py`

Add to urlpatterns:
```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...
    path('carbon-api/', include('evidence.urls')),  # Add this line
]
```

### Step 11: Run Migrations

```bash
cd backend
python manage.py makemigrations evidence
python manage.py migrate evidence
```

---

## Test Phase 1

After completing all steps, test the API:

```bash
# Start server
python manage.py runserver

# In another terminal, test (replace <token> with actual JWT):
curl -X GET "http://localhost:8000/carbon-api/evidence/" \
  -H "Authorization: Bearer <token>"

# Expected: {"count": 0, "results": []} or similar
```

---

## Acceptance Criteria

- [ ] All 11 files created
- [ ] Migrations run without errors
- [ ] API endpoint responds at `/carbon-api/evidence/`
- [ ] No Python syntax errors
- [ ] Server starts successfully

---

## Next Step

When Phase 1 is complete and all tests pass, report back: "Phase 1 complete. Ready for Phase 2."
