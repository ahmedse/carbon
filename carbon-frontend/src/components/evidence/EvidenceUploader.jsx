import React, { useState, useCallback } from 'react';
import { Box, Button, Typography, LinearProgress, Alert, List, ListItem, ListItemText, ListItemIcon } from '@mui/material';
import { CloudUpload as UploadIcon, CheckCircle as SuccessIcon, Error as ErrorIcon } from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { API_BASE_URL } from '../../config';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const ALLOWED_TYPES = {
  'application/pdf': [],
  'image/jpeg': [],
  'image/png': [],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': [],
  'text/csv': [],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': []
};

export default function EvidenceUploader({ dataRowId, token, onUploadComplete }) {
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
