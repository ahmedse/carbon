// src/pages/catalog/ImportsDetailPage.jsx
// Imports: Import job history and upload wizard
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
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
import { useNotes } from '../../notes/NotesContext';
import { registerImportInspectorTabs } from '../../inspector/tabs/collectionTabs';

export default function ImportsDetailPage() {
  useDocumentTitle("Imports");
  const { t } = useTranslation('catalog');
  const { token } = useAuth();
  const { notify } = useNotification();
  const { setContexts } = useNotes();

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
      const msg = err.message || t('importsLoadError');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleFileChange = (e) => {
    setUploadForm({ ...uploadForm, file: e.target.files[0] });
  };

  const handleUpload = async () => {
    if (!uploadForm.table_id) {
      notify({ message: t('selectTable'), type: 'error' });
      return;
    }
    if (!uploadForm.file) {
      notify({ message: t('selectFile'), type: 'error' });
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
      notify({ message: t('importStarted'), type: 'success' });
      setUploadForm({ table_id: '', file: null, format: 'excel' });
      loadData();
    } catch (err) {
      const msg = err.message || t('uploadFailed');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setUploading(false);
    }
  };

  const UploadTab = () => (
    <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth>
              <InputLabel>{t('targetTable')}</InputLabel>
              <Select
                value={uploadForm.table_id}
                label={t('targetTable')}
                onChange={(e) => setUploadForm({ ...uploadForm, table_id: e.target.value })}
              >
                {tables.map((t) => (
                  <MenuItem key={t.id} value={t.id}>{t.title}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel>{t('format')}</InputLabel>
              <Select
                value={uploadForm.format}
                label={t('format')}
                onChange={(e) => setUploadForm({ ...uploadForm, format: e.target.value })}
              >
                <MenuItem value="excel">{t('excel')}</MenuItem>
                <MenuItem value="csv">{t('csv')}</MenuItem>
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
                  ✓ {t('fileSelected', { name: uploadForm.file.name })}
                </Typography>
              )}
            </Box>

            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleUpload}
              disabled={uploading || !uploadForm.file || !uploadForm.table_id}
            >
              {uploading ? t('uploading') : t('uploadFile')}
            </Button>
          </Box>
  );

  const HistoryTab = () => (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6" fontWeight={700}>{t('importHistory')}</Typography>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={loadData}>
          {t('refresh')}
        </Button>
      </Box>
      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: 'action.hover' }}>
              <TableCell fontWeight={600}>{t('table')}</TableCell>
              <TableCell fontWeight={600}>{t('status')}</TableCell>
              <TableCell fontWeight={600}>{t('rows')}</TableCell>
              <TableCell fontWeight={600}>{t('errors')}</TableCell>
              <TableCell fontWeight={600}>{t('date')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {jobs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">{t('noImportJobs')}</Typography>
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
      { title: t('jobs'), value: jobs.length },
      { title: t('tables'), value: tables.length },
      { title: t('pending'), value: jobs.filter((job) => job.status === 'pending').length },
      { title: t('failed'), value: jobs.filter((job) => job.status === 'failed').length },
    ],
    [jobs, tables, t]
  );

  // ── Contextual Inspector (global drawer) ────────────────────────────
  // Collection pages have no single entity; anchor to a stable sentinel id (0)
  // so the summary tab renders and notes stay scoped to this collection.
  useEffect(() => registerImportInspectorTabs(), []);

  const inspectorContext = useMemo(
    () => [{ entityType: 'import', entityId: 0, label: t('imports'), payload: { summaryCards } }],
    [summaryCards, t],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  const headerComponent = (
    <DetailHeader
      title={t('imports')}
      description={t('importsDescription')}
      icon={CloudUploadIcon}
      onClose={() => window.history.back()}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: t('upload'), component: UploadTab },
        { label: t('history'), component: HistoryTab },
      ]}
      loading={loading}
      error={error}
      onClose={() => window.history.back()}
      storageKey="carbonImportsDetail"
    />
  );
}
