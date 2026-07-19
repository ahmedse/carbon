// File: src/pages/dataschema/tabs/RowOverviewTab.jsx
// Read-only overview of row data with metadata

import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Divider,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  Stack,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';

export default function RowOverviewTab({ rowData, onRefresh, onClose }) {
  const handleEdit = () => {
    // Switch to edit tab (handled by parent)
    window.dispatchEvent(
      new CustomEvent('switchTab', { detail: { tab: 1 } })
    );
  };

  const handleDelete = () => {
    window.dispatchEvent(new CustomEvent('deleteRow'));
  };

  // Extract metadata and field data
  const metadataFields = ['created_at', 'updated_at', 'created_by', 'updated_by'];
  const nonDataFields = ['id', 'data_table', 'is_archived', 'version', 'values', ...metadataFields];
  const metadata = {};
  const fieldData = {};

  // Extract metadata
  Object.entries(rowData).forEach(([key, value]) => {
    if (metadataFields.includes(key)) {
      metadata[key] = value;
    }
  });

  // Extract field data from the 'values' object
  if (rowData.values && typeof rowData.values === 'object') {
    Object.entries(rowData.values).forEach(([key, value]) => {
      fieldData[key] = value;
    });
  }

  // Fallback: if values is not nested, extract from rowData
  if (Object.keys(fieldData).length === 0) {
    Object.entries(rowData).forEach(([key, value]) => {
      if (!nonDataFields.includes(key)) {
        fieldData[key] = value;
      }
    });
  }

  const convertRowToCSV = (data) => {
    const keys = Object.keys(data);
    const headers = keys.join(',');
    const values = keys
      .map((k) => {
        const v = data[k];
        if (typeof v === 'string' && v.includes(',')) {
          return `"${v.replace(/"/g, '""')}"`;
        }
        return v;
      })
      .join(',');
    return `${headers}\n${values}`;
  };

  const handleDownload = () => {
    const csv = convertRowToCSV(fieldData);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `row-${rowData.id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Box sx={{ maxWidth: '800px' }}>
      {/* Action buttons */}
      <Box sx={{ mb: 3, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <ButtonGroup variant="outlined" size="small">
          <Button
            startIcon={<EditIcon />}
            onClick={handleEdit}
            title="Switch to edit mode"
          >
            Edit
          </Button>
          <Button
            startIcon={<DeleteIcon />}
            onClick={handleDelete}
            color="error"
            title="Delete this row"
          >
            Delete
          </Button>
          <Button
            startIcon={<DownloadIcon />}
            onClick={handleDownload}
            title="Download as CSV"
          >
            Download
          </Button>
          <Button
            startIcon={<RefreshIcon />}
            onClick={onRefresh}
            title="Refresh row data"
          >
            Refresh
          </Button>
        </ButtonGroup>
      </Box>

      {/* Data fields */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
            Row Data
          </Typography>
          <Grid container spacing={2}>
            {Object.entries(fieldData).map(([key, value]) => (
              <Grid item xs={12} sm={6} key={key}>
                <Box>
                  <Typography
                    variant="caption"
                    sx={{
                      display: 'block',
                      fontWeight: 600,
                      color: '#666',
                      textTransform: 'capitalize',
                      mb: 0.5,
                    }}
                  >
                    {key.replace(/_/g, ' ')}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      color: '#1a1a1a',
                      wordBreak: 'break-word',
                      fontFamily: 'monospace',
                      fontSize: '0.9rem',
                    }}
                  >
                    {value !== null && value !== undefined
                      ? String(value)
                      : '(empty)'}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>

      {/* Metadata */}
      {Object.keys(metadata).length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
              Metadata
            </Typography>
            <Stack spacing={1.5}>
              {metadata.created_at && (
                <Box>
                  <Typography
                    variant="caption"
                    sx={{
                      display: 'block',
                      fontWeight: 600,
                      color: '#666',
                      mb: 0.3,
                    }}
                  >
                    Created
                  </Typography>
                  <Typography variant="body2">
                    {new Date(metadata.created_at).toLocaleString()}
                  </Typography>
                </Box>
              )}
              {metadata.updated_at && (
                <Box>
                  <Typography
                    variant="caption"
                    sx={{
                      display: 'block',
                      fontWeight: 600,
                      color: '#666',
                      mb: 0.3,
                    }}
                  >
                    Last Modified
                  </Typography>
                  <Typography variant="body2">
                    {new Date(metadata.updated_at).toLocaleString()}
                  </Typography>
                </Box>
              )}
              {metadata.created_by && (
                <Box>
                  <Typography
                    variant="caption"
                    sx={{
                      display: 'block',
                      fontWeight: 600,
                      color: '#666',
                      mb: 0.3,
                    }}
                  >
                    Created By
                  </Typography>
                  <Typography variant="body2">{metadata.created_by}</Typography>
                </Box>
              )}
              {metadata.updated_by && (
                <Box>
                  <Typography
                    variant="caption"
                    sx={{
                      display: 'block',
                      fontWeight: 600,
                      color: '#666',
                      mb: 0.3,
                    }}
                  >
                    Modified By
                  </Typography>
                  <Typography variant="body2">{metadata.updated_by}</Typography>
                </Box>
              )}
            </Stack>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
