# TASK A8 - PHASE 2: Frontend Evidence Components

**Phase:** 2 of 5  
**Objective:** Create React components for file upload and evidence viewing  
**Estimated Time:** 30 minutes

---

## What to Build

Two React components:
1. **EvidenceUploader** - Drag-and-drop file upload
2. **EvidenceViewer** - List/download/delete evidence

---

## Step-by-Step Instructions

### Step 1: Install Dependency

```bash
cd carbon-frontend
npm install react-dropzone
```

### Step 2: Create Evidence Directory

```bash
mkdir -p src/components/evidence
```

### Step 3: Create EvidenceUploader Component

File: `carbon-frontend/src/components/evidence/EvidenceUploader.jsx`

```jsx
import React, { useState, useCallback } from 'react';
import { Box, Button, Typography, LinearProgress, Alert, List, ListItem, ListItemText, ListItemIcon } from '@mui/material';
import { CloudUpload as UploadIcon, CheckCircle as SuccessIcon, Error as ErrorIcon } from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { API_BASE_URL } from '../../config';
import { useAuth } from '../../hooks/useAuth';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const ALLOWED_TYPES = {
  'application/pdf': [],
  'image/jpeg': [],
  'image/png': [],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': [],
  'text/csv': [],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': []
};

export default function EvidenceUploader({ dataRowId, onUploadComplete }) {
  const { token } = useAuth();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  const onDrop = useCallback(async (acceptedFiles, rejectedFiles) => {
    setError(null);
    setResults([]);

    if (rejectedFiles.length > 0) {
      setError(`Rejected: ${rejectedFiles.map(f => f.file.name).join(', ')}`);
      return;
    }

    const formData = new FormData();
    formData.append('data_row', dataRowId);
    acceptedFiles.forEach(file => formData.append('files', file));

    setUploading(true);
    setProgress(0);

    try {
      const response = await fetch(`${API_BASE_URL}/carbon-api/evidence/bulk-upload/`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      const data = await response.json();
      if (response.ok) {
        setResults(data.results);
        setProgress(100);
        if (onUploadComplete) onUploadComplete(data.results.filter(r => r.status === 'success'));
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
    accept: ALLOWED_TYPES
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
          '&:hover': { borderColor: 'primary.main', bgcolor: 'action.hover' }
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
        <Typography variant="caption" color="text.secondary">Max: 50MB</Typography>
      </Box>

      {uploading && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2">Uploading...</Typography>
          <LinearProgress variant="determinate" value={progress} />
        </Box>
      )}

      {error && <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      {results.length > 0 && (
        <List sx={{ mt: 2 }}>
          {results.map((result, idx) => (
            <ListItem key={idx}>
              <ListItemIcon>
                {result.status === 'success' ? <SuccessIcon color="success" /> : <ErrorIcon color="error" />}
              </ListItemIcon>
              <ListItemText
                primary={result.filename}
                secondary={result.status === 'error' ? 'Failed' : 'Success'}
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  );
}
```

### Step 4: Create EvidenceViewer Component

File: `carbon-frontend/src/components/evidence/EvidenceViewer.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import { Box, Typography, List, ListItem, ListItemText, ListItemIcon, IconButton, CircularProgress, Alert } from '@mui/material';
import { InsertDriveFile as FileIcon, Download as DownloadIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { API_BASE_URL } from '../../config';
import { useAuth } from '../../hooks/useAuth';

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
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
      const response = await fetch(`${API_BASE_URL}/carbon-api/evidence/?data_row=${dataRowId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

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
      const response = await fetch(`${API_BASE_URL}/carbon-api/evidence/${evidenceId}/download/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

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
    if (!confirm('Delete this evidence?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/carbon-api/evidence/${evidenceId}/`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        setEvidence(prev => prev.filter(e => e.id !== evidenceId));
        if (onDelete) onDelete(evidenceId);
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress /></Box>;
  if (error) return <Alert severity="error">{error}</Alert>;
  if (evidence.length === 0) {
    return <Box sx={{ p: 3, textAlign: 'center' }}><Typography variant="body2" color="text.secondary">No evidence yet</Typography></Box>;
  }

  return (
    <List>
      {evidence.map((item) => (
        <ListItem
          key={item.id}
          secondaryAction={
            <Box>
              <IconButton size="small" onClick={() => handleDownload(item.id, item.original_filename)} title="Download">
                <DownloadIcon />
              </IconButton>
              <IconButton size="small" onClick={() => handleDelete(item.id)} title="Delete">
                <DeleteIcon />
              </IconButton>
            </Box>
          }
        >
          <ListItemIcon><FileIcon /></ListItemIcon>
          <ListItemText
            primary={item.original_filename}
            secondary={
              <>
                {formatFileSize(item.file_size)} • {formatDate(item.uploaded_at)}
                <br />
                By {item.uploaded_by_name}
              </>
            }
          />
        </ListItem>
      ))}
    </List>
  );
}
```

---

## Test Phase 2

```bash
# Build to check for errors
cd carbon-frontend
npm run build
```

---

## Acceptance Criteria

- [ ] react-dropzone installed in package.json
- [ ] Both components created
- [ ] Build completes without errors
- [ ] No console errors in terminal

---

## Next Step

When Phase 2 is complete, report back: "Phase 2 complete. Ready for Phase 3."
