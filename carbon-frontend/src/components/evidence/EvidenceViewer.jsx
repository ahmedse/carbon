import React, { useState, useEffect } from 'react';
import { Box, Typography, List, ListItem, ListItemText, ListItemIcon, IconButton, CircularProgress, Alert } from '@mui/material';
import { InsertDriveFile as FileIcon, Download as DownloadIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { authFetch } from '../../api/api';

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

export default function EvidenceViewer({ dataRowId, token, onDelete }) {
  const [evidence, setEvidence] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchEvidence = async () => {
    if (!dataRowId) return;
    setLoading(true);
    setError(null);

    try {
      const response = await authFetch(`evidence/?data_row=${dataRowId}`, {
        method: 'GET',
      });

      console.log('🟦 EvidenceViewer: Fetch response', {
        status: response.status,
        ok: response.ok,
        dataRowId,
      });

      if (response.status === 401) {
        console.error('🔴 EvidenceViewer: 401 Unauthorized - token may be invalid or expired');
        localStorage.removeItem('access');
        localStorage.removeItem('refresh');
        setError('Authentication failed. Please refresh the page or log in again.');
      } else if (response.ok) {
        const data = await response.json();
        setEvidence(data.results || data);
        console.log('🟩 EvidenceViewer: Evidence loaded', { count: (data.results || data).length });
      } else {
        console.error('🔴 EvidenceViewer: HTTP error', { status: response.status, statusText: response.statusText });
        setError(`Failed to load evidence (${response.status})`);
      }
    } catch (err) {
      console.error('🔴 EvidenceViewer: Fetch error', err);
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvidence();
  }, [dataRowId, token]);

  useEffect(() => {
    const onEvidenceRefresh = (event) => {
      if (!event?.detail || event.detail.rowId !== dataRowId) return;
      fetchEvidence();
    };

    window.addEventListener('evidenceRefresh', onEvidenceRefresh);
    return () => window.removeEventListener('evidenceRefresh', onEvidenceRefresh);
  }, [dataRowId, token]);

  const handleDownload = async (evidenceId, filename) => {
    try {
      const response = await authFetch(`evidence/${evidenceId}/download/`, {
        method: 'GET',
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
      const response = await authFetch(`evidence/${evidenceId}/`, {
        method: 'DELETE',
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
