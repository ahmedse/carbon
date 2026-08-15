// src/pages/catalog/ImportsDetailPage.jsx
// Imports: Import job history and upload wizard
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from '@mui/icons-material/Add';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import RefreshIcon from '@mui/icons-material/Refresh';
import { fetchImportJobs, createImportJob } from '../../api/catalog';
import { fetchDataSchemaTables } from '../../api/dataschema';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import HomeIcon from '@mui/icons-material/Home';

export default function ImportsDetailPage() {
  useDocumentTitle("Imports");
  const { token } = useAuth();
  const { notify } = useNotification();

  const [jobs, setJobs] = useState([]);
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const [uploadForm, setUploadForm] = useState({
    table_id: '',
    file: null,
    format: 'excel'
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [jobsData, tablesData] = await Promise.all([
        fetchImportJobs(token),
        fetchDataSchemaTables(token, null, null)
      ]);
      setJobs(Array.isArray(jobsData) ? jobsData : (jobsData?.results || []));
      setTables(Array.isArray(tablesData) ? tablesData : (tablesData?.results || []));
    } catch (err) {
      const msg = err.message || 'Failed to load imports';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleFileChange = (e) => {
    setUploadForm({ ...uploadForm, file: e.target.files[0] });
  };

  const handleUpload = async () => {
    if (!uploadForm.table_id) {
      notify({ message: 'Please select a table', type: 'error' });
      return;
    }
    if (!uploadForm.file) {
      notify({ message: 'Please select a file', type: 'error' });
      return;
    }

    setUploading(true);
    setError(null);
    try {
      await createImportJob(token, {
        table_id: uploadForm.table_id,
        file: uploadForm.file,
        format: uploadForm.format
      });
      notify({ message: 'Import started', type: 'success' });
      setUploadForm({ table_id: '', file: null, format: 'excel' });
      loadData();
    } catch (err) {
      const msg = err.message || 'Upload failed';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setUploading(false);
    }
  };

  const UploadTab = () => (
    <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Target Table</InputLabel>
              <Select
                value={uploadForm.table_id}
                label="Target Table"
                onChange={(e) => setUploadForm({ ...uploadForm, table_id: e.target.value })}
              >
                {tables.map((t) => (
                  <MenuItem key={t.id} value={t.id}>{t.title}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel>Format</InputLabel>
              <Select
                value={uploadForm.format}
                label="Format"
                onChange={(e) => setUploadForm({ ...uploadForm, format: e.target.value })}
              >
                <MenuItem value="excel">Excel</MenuItem>
                <MenuItem value="csv">CSV</MenuItem>
              </Select>
            </FormControl>

            <Box>
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                onChange={handleFileChange}
                style={{ marginBottom: '1rem' }}
              />
              {uploadForm.file && (
                <Typography variant="caption" color="success.main">
                  ✓ {uploadForm.file.name} selected
                </Typography>
              )}
            </Box>

            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleUpload}
              disabled={uploading || !uploadForm.file || !uploadForm.table_id}
            >
              {uploading ? 'Uploading...' : 'Upload File'}
            </Button>
          </Box>
  );

  const HistoryTab = () => (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6" fontWeight={700}>Import History</Typography>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={loadData}>
          Refresh
        </Button>
      </Box>
      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: 'action.hover' }}>
              <TableCell fontWeight={600}>Table</TableCell>
              <TableCell fontWeight={600}>Status</TableCell>
              <TableCell fontWeight={600}>Rows</TableCell>
              <TableCell fontWeight={600}>Errors</TableCell>
              <TableCell fontWeight={600}>Date</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {jobs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">No import jobs</Typography>
                </TableCell>
              </TableRow>
            ) : (
              jobs.map((job) => (
                <TableRow key={job.id} hover>
                  <TableCell>{job.data_table_title || '—'}</TableCell>
                  <TableCell>
                    <Chip
                      label={job.status}
                      size="small"
                      color={job.status === 'done' ? 'success' : job.status === 'failed' ? 'error' : 'default'}
                      variant={job.status === 'done' || job.status === 'failed' ? 'filled' : 'outlined'}
                    />
                  </TableCell>
                  <TableCell>{job.row_count || 0}</TableCell>
                  <TableCell>{job.error_count || 0}</TableCell>
                  <TableCell>
                    <Typography variant="caption">
                      {job.created_at ? new Date(job.created_at).toLocaleDateString() : '—'}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );

  const summaryCards = useMemo(
    () => [
      { title: 'Jobs', value: jobs.length },
      { title: 'Tables', value: tables.length },
      { title: 'Pending', value: jobs.filter((job) => job.status === 'pending').length },
      { title: 'Failed', value: jobs.filter((job) => job.status === 'failed').length },
    ],
    [jobs, tables]
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  const headerComponent = (
    <DetailHeader
      title="Imports"
      description="Upload data and manage import jobs"
      icon={CloudUploadIcon}
      onClose={() => window.history.back()}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Upload', component: UploadTab },
        { label: 'History', component: HistoryTab },
      ]}
      metricsTabs={[{ label: 'Summary', component: () => (
        <Box sx={{ p: 2 }}>
          {summaryCards.map((card) => (
            <Box key={card.title} sx={{ p: 2, mb: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
              <Typography variant="caption" color="text.secondary">{card.title}</Typography>
              <Typography variant="h6">{card.value}</Typography>
            </Box>
          ))}
        </Box>
      ) }]}
      loading={loading}
      error={error}
      onClose={() => window.history.back()}
      storageKey="carbonImportsDetail"
      entityData={{ jobs, tables }}
    />
  );
}
