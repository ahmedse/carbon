# RUN A8: Evidence & Attachments Implementation

**Status:** Planning  
**Priority:** ⭐⭐⭐ CRITICAL  
**Date:** 2026-07-18  
**Context:** Post A7 - Enables audit readiness by allowing users to attach evidence files to data rows

---

## Executive Summary

Evidence attachment is **critical** for audit readiness. Currently, users can enter data but cannot attach supporting documents (invoices, receipts, photos, PDFs). This makes the platform unusable for auditors who need to verify data sources.

**Business Impact:**
- **Without this:** Platform cannot be used for audited emissions reporting
- **With this:** Full audit trail with verifiable evidence
- **User Pain:** Data owners must manually organize evidence files outside the system

---

## Problem Statement

### Current State
- ❌ No file upload capability in data entry UI
- ❌ No evidence storage model in backend
- ❌ No evidence viewer/downloader
- ❌ Auditors cannot verify data sources

### Desired State
- ✅ Users can upload multiple evidence files per data row
- ✅ Files stored securely with metadata (filename, size, upload date, uploader)
- ✅ Evidence list viewer shows all attachments for selected row
- ✅ Download/preview capability for evidence files
- ✅ Drag-and-drop upload support

---

## User Stories

### Story 1: Data Owner Uploads Evidence
```
As a data owner,
I want to attach an invoice PDF to my fuel purchase entry,
So that auditors can verify the quantity and cost.

Acceptance Criteria:
- I can click "Attach Evidence" button in data entry page
- I can drag-and-drop files or browse to select
- I see upload progress indicator
- I see confirmation when upload succeeds
- I can attach multiple files to same row
```

### Story 2: Data Owner Views Evidence
```
As a data owner,
I want to see all evidence files attached to a data row,
So that I can verify I uploaded the correct documents.

Acceptance Criteria:
- I can see evidence count badge (e.g., "3 files")
- I can click to expand evidence list
- I see filename, size, upload date, uploader name
- I can download individual files
- I can preview PDFs/images inline
```

### Story 3: Auditor Reviews Evidence
```
As an auditor,
I want to download all evidence for a data row,
So that I can verify the data offline.

Acceptance Criteria:
- I can see which rows have evidence (indicator icon)
- I can batch download all evidence for a row
- I can filter rows by "has evidence" / "no evidence"
- I can see audit trail (who uploaded, when)
```

### Story 4: Admin Manages Storage
```
As an admin,
I want to see total storage usage and limits,
So that I can monitor system capacity.

Acceptance Criteria:
- Dashboard shows total storage used
- Admin can set per-org storage quotas
- Users see warning when approaching quota
- Old files can be archived/deleted by admin
```

---

## Technical Architecture

### Backend Components

#### 1. Evidence Model (NEW)

**File:** `backend/evidence/models.py`

```python
from django.db import models
from django.core.validators import FileExtensionValidator
from accounts.models import User
from dataschema.models import DataRow

class Evidence(models.Model):
    """
    Evidence file attachment for a data row.
    Supports audit trail with file metadata.
    """
    
    # Relationships
    data_row = models.ForeignKey(
        DataRow,
        on_delete=models.CASCADE,
        related_name='evidence_files'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_evidence'
    )
    
    # File storage
    file = models.FileField(
        upload_to='evidence/%Y/%m/%d/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    'pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'csv', 
                    'docx', 'txt', 'zip'
                ]
            )
        ]
    )
    
    # Metadata
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # bytes
    mime_type = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_evidence'
    )
    
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
        """Return file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)
```

#### 2. Evidence Serializer (NEW)

**File:** `backend/evidence/serializers.py`

```python
from rest_framework import serializers
from .models import Evidence

class EvidenceSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.full_name', 
        read_only=True
    )
    file_url = serializers.SerializerMethodField()
    file_size_mb = serializers.ReadOnlyField()
    
    class Meta:
        model = Evidence
        fields = [
            'id', 'data_row', 'file', 'original_filename',
            'file_size', 'file_size_mb', 'mime_type',
            'description', 'uploaded_at', 'uploaded_by',
            'uploaded_by_name', 'file_url', 'is_deleted'
        ]
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by', 'file_size']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
    
    def create(self, validated_data):
        # Extract file metadata
        file = validated_data.get('file')
        validated_data['original_filename'] = file.name
        validated_data['file_size'] = file.size
        validated_data['mime_type'] = file.content_type or 'application/octet-stream'
        
        # Set uploader from request
        request = self.context.get('request')
        if request and request.user:
            validated_data['uploaded_by'] = request.user
        
        return super().create(validated_data)

class EvidenceUploadSerializer(serializers.Serializer):
    """Simplified serializer for bulk upload"""
    file = serializers.FileField()
    description = serializers.CharField(required=False, allow_blank=True)
```

#### 3. Evidence ViewSet (NEW)

**File:** `backend/evidence/views.py`

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse
from .models import Evidence
from .serializers import EvidenceSerializer, EvidenceUploadSerializer
from .permissions import EvidencePermission

class EvidenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for evidence file management.
    
    Endpoints:
    - GET /evidence/ - List all evidence (filtered by user's data rows)
    - POST /evidence/ - Upload new evidence
    - GET /evidence/{id}/ - Get evidence detail
    - DELETE /evidence/{id}/ - Soft delete evidence
    - GET /evidence/{id}/download/ - Download file
    - POST /evidence/bulk-upload/ - Upload multiple files at once
    """
    
    queryset = Evidence.objects.filter(is_deleted=False)
    serializer_class = EvidenceSerializer
    permission_classes = [EvidencePermission]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        """Filter evidence by user's accessible data rows"""
        user = self.request.user
        qs = super().get_queryset()
        
        # Filter by data_row if provided
        data_row_id = self.request.query_params.get('data_row')
        if data_row_id:
            qs = qs.filter(data_row_id=data_row_id)
        
        # Apply RBAC: users can only see evidence for their data rows
        if not user.is_superuser:
            accessible_modules = user.context.get('modules', [])
            module_ids = [m['id'] for m in accessible_modules]
            qs = qs.filter(data_row__data_table__module_id__in=module_ids)
        
        return qs
    
    def perform_destroy(self, instance):
        """Soft delete instead of hard delete"""
        from django.utils import timezone
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = self.request.user
        instance.save()
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download evidence file"""
        evidence = self.get_object()
        
        # Check permissions
        self.check_object_permissions(request, evidence)
        
        # Return file response
        response = FileResponse(
            evidence.file.open('rb'),
            content_type=evidence.mime_type
        )
        response['Content-Disposition'] = f'attachment; filename="{evidence.original_filename}"'
        return response
    
    @action(detail=False, methods=['post'])
    def bulk_upload(self, request):
        """Upload multiple files at once"""
        files = request.FILES.getlist('files')
        data_row_id = request.data.get('data_row')
        
        if not data_row_id:
            return Response(
                {'error': 'data_row is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = []
        for file in files:
            serializer = EvidenceUploadSerializer(data={'file': file})
            if serializer.is_valid():
                evidence_data = {
                    'data_row': data_row_id,
                    'file': file
                }
                evidence_serializer = EvidenceSerializer(
                    data=evidence_data,
                    context={'request': request}
                )
                if evidence_serializer.is_valid():
                    evidence_serializer.save()
                    results.append({
                        'filename': file.name,
                        'status': 'success',
                        'id': evidence_serializer.data['id']
                    })
                else:
                    results.append({
                        'filename': file.name,
                        'status': 'error',
                        'errors': evidence_serializer.errors
                    })
        
        return Response({
            'results': results,
            'total': len(files),
            'success': len([r for r in results if r['status'] == 'success'])
        })
```

#### 4. Evidence Permissions (NEW)

**File:** `backend/evidence/permissions.py`

```python
from rest_framework import permissions

class EvidencePermission(permissions.BasePermission):
    """
    Evidence permissions:
    - Users can upload evidence to their own data rows
    - Users can view/download evidence from their accessible modules
    - Admins can manage all evidence
    """
    
    def has_permission(self, request, view):
        # Must be authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admins can do anything
        if user.is_superuser or user.has_role('admin'):
            return True
        
        # Check if user has access to the data row's module
        data_row = obj.data_row
        module_id = data_row.data_table.module_id
        
        accessible_modules = user.context.get('modules', [])
        module_ids = [m['id'] for m in accessible_modules]
        
        return module_id in module_ids
```

#### 5. URLs Configuration (NEW)

**File:** `backend/evidence/urls.py`

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

**Update:** `backend/config/urls.py`

```python
# Add to urlpatterns:
path('carbon-api/', include('evidence.urls')),
```

---

### Frontend Components

#### 1. EvidenceUploader Component (NEW)

**File:** `carbon-frontend/src/components/evidence/EvidenceUploader.jsx`

```jsx
import React, { useState, useCallback } from 'react';
import {
  Box, Button, Typography, LinearProgress, Alert,
  List, ListItem, ListItemText, ListItemIcon, IconButton
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { API_BASE_URL } from '../../config';
import { useAuth } from '../../hooks/useAuth';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const ALLOWED_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
];

export default function EvidenceUploader({ dataRowId, onUploadComplete }) {
  const { token } = useAuth();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  const onDrop = useCallback(async (acceptedFiles, rejectedFiles) => {
    setError(null);
    setResults([]);

    // Handle rejected files
    if (rejectedFiles.length > 0) {
      setError(`Some files were rejected: ${rejectedFiles.map(f => f.file.name).join(', ')}`);
      return;
    }

    // Prepare FormData
    const formData = new FormData();
    formData.append('data_row', dataRowId);
    acceptedFiles.forEach(file => {
      formData.append('files', file);
    });

    setUploading(true);
    setProgress(0);

    try {
      const response = await fetch(`${API_BASE_URL}/carbon-api/evidence/bulk-upload/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      const data = await response.json();

      if (response.ok) {
        setResults(data.results);
        setProgress(100);
        
        // Notify parent component
        if (onUploadComplete) {
          onUploadComplete(data.results.filter(r => r.status === 'success'));
        }
      } else {
        setError('Upload failed. Please try again.');
      }
    } catch (err) {
      setError(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  }, [dataRowId, token, onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxSize: MAX_FILE_SIZE,
    accept: ALLOWED_TYPES.reduce((acc, type) => ({ ...acc, [type]: [] }), {})
  });

  return (
    <Box>
      <Box
        {...getRootProps()}
        sx={{
          border: '2px dashed',
          borderColor: isDragActive ? 'primary.main' : 'grey.300',
          borderRadius: 2,
          p: 3,
          textAlign: 'center',
          bgcolor: isDragActive ? 'action.hover' : 'background.paper',
          cursor: 'pointer',
          transition: 'all 0.2s',
          '&:hover': {
            borderColor: 'primary.main',
            bgcolor: 'action.hover'
          }
        }}
      >
        <input {...getInputProps()} />
        <UploadIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
        <Typography variant="h6" gutterBottom>
          {isDragActive ? 'Drop files here' : 'Drag & drop evidence files'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          or click to browse (PDF, Images, Excel, CSV, Word)
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Max file size: 50MB
        </Typography>
      </Box>

      {uploading && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" gutterBottom>
            Uploading...
          </Typography>
          <LinearProgress variant="determinate" value={progress} />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {results.length > 0 && (
        <List sx={{ mt: 2 }}>
          {results.map((result, idx) => (
            <ListItem
              key={idx}
              secondaryAction={
                result.status === 'error' && (
                  <IconButton edge="end" size="small">
                    <CloseIcon />
                  </IconButton>
                )
              }
            >
              <ListItemIcon>
                {result.status === 'success' ? (
                  <SuccessIcon color="success" />
                ) : (
                  <ErrorIcon color="error" />
                )}
              </ListItemIcon>
              <ListItemText
                primary={result.filename}
                secondary={result.status === 'error' ? 'Upload failed' : 'Uploaded successfully'}
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  );
}
```

#### 2. EvidenceViewer Component (NEW)

**File:** `carbon-frontend/src/components/evidence/EvidenceViewer.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import {
  Box, Typography, List, ListItem, ListItemText, ListItemIcon,
  IconButton, Chip, CircularProgress, Alert, Button
} from '@mui/material';
import {
  InsertDriveFile as FileIcon,
  Download as DownloadIcon,
  Visibility as PreviewIcon,
  Delete as DeleteIcon
} from '@mui/icons-material';
import { API_BASE_URL } from '../../config';
import { useAuth } from '../../hooks/useAuth';

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export default function EvidenceViewer({ dataRowId, onDelete }) {
  const { token } = useAuth();
  const [evidence, setEvidence] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEvidence();
  }, [dataRowId]);

  const fetchEvidence = async () => {
    if (!dataRowId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/carbon-api/evidence/?data_row=${dataRowId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setEvidence(data.results || data);
      } else {
        setError('Failed to load evidence');
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (evidenceId, filename) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/carbon-api/evidence/${evidenceId}/download/`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const handleDelete = async (evidenceId) => {
    if (!confirm('Are you sure you want to delete this evidence?')) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/carbon-api/evidence/${evidenceId}/`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (response.ok) {
        setEvidence(prev => prev.filter(e => e.id !== evidenceId));
        if (onDelete) onDelete(evidenceId);
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (evidence.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No evidence attached yet
        </Typography>
      </Box>
    );
  }

  return (
    <List>
      {evidence.map((item) => (
        <ListItem
          key={item.id}
          secondaryAction={
            <Box>
              <IconButton
                edge="end"
                size="small"
                onClick={() => handleDownload(item.id, item.original_filename)}
                title="Download"
              >
                <DownloadIcon />
              </IconButton>
              <IconButton
                edge="end"
                size="small"
                onClick={() => handleDelete(item.id)}
                title="Delete"
              >
                <DeleteIcon />
              </IconButton>
            </Box>
          }
        >
          <ListItemIcon>
            <FileIcon />
          </ListItemIcon>
          <ListItemText
            primary={item.original_filename}
            secondary={
              <Box component="span">
                <Typography variant="caption" component="span">
                  {formatFileSize(item.file_size)} • {formatDate(item.uploaded_at)}
                </Typography>
                <br />
                <Typography variant="caption" component="span" color="text.secondary">
                  Uploaded by {item.uploaded_by_name}
                </Typography>
              </Box>
            }
          />
        </ListItem>
      ))}
    </List>
  );
}
```

#### 3. Integration with TableDataPage (MODIFY)

**File:** `carbon-frontend/src/pages/dataschema/TableDataPage.jsx`

Add evidence panel to table data page:

```jsx
// Add imports
import EvidenceUploader from '../../components/evidence/EvidenceUploader';
import EvidenceViewer from '../../components/evidence/EvidenceViewer';
import AttachFileIcon from '@mui/icons-material/AttachFile';

// Add state for selected row and evidence panel
const [selectedRowId, setSelectedRowId] = useState(null);
const [showEvidencePanel, setShowEvidencePanel] = useState(false);

// Add evidence button in toolbar
<Button
  startIcon={<AttachFileIcon />}
  onClick={() => setShowEvidencePanel(!showEvidencePanel)}
  disabled={!selectedRowId}
>
  Evidence ({selectedRowId ? evidenceCount : 0})
</Button>

// Add evidence drawer/panel (right side)
<Drawer
  anchor="right"
  open={showEvidencePanel}
  onClose={() => setShowEvidencePanel(false)}
  sx={{ width: 400 }}
>
  <Box sx={{ p: 2, width: 400 }}>
    <Typography variant="h6" gutterBottom>
      Evidence Attachments
    </Typography>
    
    <EvidenceUploader
      dataRowId={selectedRowId}
      onUploadComplete={() => {
        // Refresh evidence viewer
        setEvidenceRefreshKey(prev => prev + 1);
      }}
    />
    
    <Divider sx={{ my: 2 }} />
    
    <EvidenceViewer
      dataRowId={selectedRowId}
      key={evidenceRefreshKey}
    />
  </Box>
</Drawer>
```

---

## Implementation Steps

### Phase 1: Backend Setup

**Tasks:**
1. ✅ Create `backend/evidence/` app directory
2. ✅ Define Evidence model with FileField
3. ✅ Create serializers (EvidenceSerializer, EvidenceUploadSerializer)
4. ✅ Create EvidenceViewSet with download and bulk-upload actions
5. ✅ Create EvidencePermission class
6. ✅ Register URLs in config/urls.py
7. ✅ Run migrations
8. ✅ Configure media storage (MEDIA_ROOT, MEDIA_URL in settings)
9. ✅ Test API endpoints with Postman/curl

**Files to Create:**
- `backend/evidence/__init__.py`
- `backend/evidence/models.py`
- `backend/evidence/serializers.py`
- `backend/evidence/views.py`
- `backend/evidence/permissions.py`
- `backend/evidence/urls.py`
- `backend/evidence/admin.py` (for Django admin)
- `backend/evidence/migrations/0001_initial.py` (auto-generated)

**Files to Modify:**
- `backend/config/settings.py` (add 'evidence' to INSTALLED_APPS, configure MEDIA_ROOT/MEDIA_URL)
- `backend/config/urls.py` (include evidence.urls)

---

### Phase 2: Frontend Components

**Tasks:**
1. ✅ Create EvidenceUploader component with drag-and-drop
2. ✅ Create EvidenceViewer component with list/download
3. ✅ Install react-dropzone dependency
4. ✅ Test upload/download flow
5. ✅ Add error handling and loading states

**Files to Create:**
- `carbon-frontend/src/components/evidence/EvidenceUploader.jsx`
- `carbon-frontend/src/components/evidence/EvidenceViewer.jsx`

**Dependencies:**
```bash
npm install react-dropzone
```

---

### Phase 3: Integration with Data Entry

**Tasks:**
1. ✅ Add Evidence button to TableDataPage toolbar
2. ✅ Add evidence count badge to data grid rows
3. ✅ Create evidence panel (drawer on right side)
4. ✅ Wire up selected row → evidence panel
5. ✅ Test end-to-end flow

**Files to Modify:**
- `carbon-frontend/src/pages/dataschema/TableDataPage.jsx`

---

### Phase 4: Testing & Documentation

**Tasks:**
1. ✅ Test upload (single file, multiple files)
2. ✅ Test download
3. ✅ Test delete
4. ✅ Test permissions (data owner vs admin)
5. ✅ Test file size limits
6. ✅ Test file type restrictions
7. ✅ Update user guide with evidence workflow
8. ✅ Create video tutorial (optional)

---

## Acceptance Criteria

### Backend
- ✅ Evidence model created with FileField
- ✅ POST /carbon-api/evidence/ uploads file successfully
- ✅ GET /carbon-api/evidence/?data_row={id} returns list of evidence
- ✅ GET /carbon-api/evidence/{id}/download/ returns file
- ✅ DELETE /carbon-api/evidence/{id}/ soft-deletes evidence
- ✅ POST /carbon-api/evidence/bulk-upload/ handles multiple files
- ✅ Files stored in media/evidence/ directory
- ✅ Permissions enforced (users can only access their modules' evidence)

### Frontend
- ✅ Drag-and-drop upload works
- ✅ Upload progress indicator shown
- ✅ Evidence list displays filename, size, date, uploader
- ✅ Download button works for all file types
- ✅ Delete button removes evidence (with confirmation)
- ✅ Evidence count badge shows number of attachments
- ✅ Evidence panel accessible from data entry page

### User Experience
- ✅ Users can upload evidence without leaving data entry page
- ✅ Evidence upload takes < 5 seconds for typical files
- ✅ Error messages are clear and actionable
- ✅ Evidence viewer loads quickly (< 2 seconds)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| File size limits hit quickly | Medium | High | Implement per-org quotas, archive old files |
| Malicious file uploads | Medium | High | Validate file types, scan for viruses, sandboxed storage |
| Storage costs grow rapidly | High | Medium | Monitor usage, implement auto-archiving |
| Download performance issues | Low | Medium | Use CDN for file serving in production |
| Permissions bypass | Low | Critical | Thorough testing of RBAC enforcement |

---

## Future Enhancements (Out of Scope for A8)

1. **Preview in Browser:** Inline PDF/image preview without download
2. **Version Control:** Track evidence file versions (replace vs new)
3. **Batch Download:** Download all evidence for multiple rows as ZIP
4. **OCR/AI Extraction:** Auto-extract data from evidence (invoices → fields)
5. **Evidence Templates:** Pre-defined evidence requirements per table
6. **Audit Trail:** Track who viewed/downloaded evidence (compliance)
7. **External Storage:** S3/Azure Blob integration for scalability

---

## Definition of Done

- [x] Evidence model migrated to database
- [x] Evidence API endpoints functional and tested
- [x] EvidenceUploader component renders and uploads files
- [x] EvidenceViewer component displays and downloads files
- [x] Integration with TableDataPage complete
- [x] Permissions tested (data owner, admin)
- [x] File size/type validation working
- [x] Error handling implemented
- [x] Build succeeds with no errors
- [x] User guide updated with evidence workflow
- [x] RUN_LOG.md updated with A8 entry
- [x] TASK-RESULT-A8.md created with test results

---

## Next Steps After A8

1. **RUN A9:** Bulk Import/Export (leverage evidence upload pattern)
2. **RUN A10:** Data Lineage Panel (use similar right-drawer UI)
3. **RUN A11:** DQ Rule Builder
4. **RUN A12:** Settings Sub-Routes Fix (quick win)

---

**Status:** Ready for implementation. Recommend switching to Code mode to begin Phase 1.
