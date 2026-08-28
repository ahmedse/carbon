import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Box, Button, Typography, LinearProgress, Alert, List, ListItem, ListItemText, ListItemIcon } from '@mui/material';
import { CloudUpload as UploadIcon, CheckCircle as SuccessIcon, Error as ErrorIcon } from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { authFetch } from '../../api/api';

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
  const { t } = useTranslation('evidence');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  const onDrop = useCallback(async (acceptedFiles, rejectedFiles) => {
    setError(null);
    setResults([]);

    if (rejectedFiles.length > 0) {
      setError(t('rejected', { names: rejectedFiles.map(f => f.file.name).join(', ') }));
      return;
    }

    const formData = new FormData();
    formData.append('data_row', dataRowId);
    acceptedFiles.forEach(file => formData.append('files', file));

    setUploading(true);
    setProgress(0);

    try {
      const response = await authFetch(`evidence/bulk-upload/`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (response.ok) {
        setResults(data.results);
        setProgress(100);
        if (onUploadComplete) onUploadComplete(data.results.filter(r => r.status === 'success'));
      } else if (response.status === 401) {
        setError(t('authFailed'));
      } else {
        setError(data.detail || t('uploadFailed'));
      }
    } catch (err) {
      setError(t('uploadError', { message: err.message }));
    } finally {
      setUploading(false);
    }
  }, [dataRowId, onUploadComplete, t]);

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
          cursor: uploading && results.length === 0 ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s',
          opacity: uploading && results.length === 0 ? 0.5 : 1,
          pointerEvents: uploading && results.length === 0 ? 'none' : 'auto',
          '&:hover': { borderColor: uploading && results.length === 0 ? 'grey.300' : 'primary.main', bgcolor: uploading && results.length === 0 ? 'background.paper' : 'action.hover' }
        }}
      >
        <input {...getInputProps()} disabled={uploading && results.length === 0} />
        <UploadIcon sx={{ fontSize: '3rem', color: 'primary.main', mb: 2 }} />
        <Typography variant="h6" gutterBottom>
          {isDragActive ? t('dropHere') : t('dragDrop')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('browseHint')}
        </Typography>
        <Typography variant="caption" color="text.secondary">{t('maxSize')}</Typography>
      </Box>

      {uploading && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2">{t('uploading')}</Typography>
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
                secondary={result.status === 'error' ? t('failed') : t('success')}
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  );
}
