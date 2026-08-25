// src/pages/catalog/ImportExportPage.jsx
// Catalog: Manage bulk import/export of data (jobs and reusable export projects)

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
  fetchExportProjects,
  createExportProject,
  updateExportProject,
  deleteExportProject,
  runExportProject,
  fetchImportJobs,
  createImportJob,
  fetchExportJobs,
  getExportJobDownloadUrl,
  fetchDataSources,
} from '../../api/catalog';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import { fetchDataSchemaTables } from '../../api/dataschema';
import PageHeader from '../../components/Page/PageHeader';
import {
  Box,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Typography,
  Tabs,
  Tab,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Card,
  CardContent,
  CardActions,
  Input,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DownloadIcon from '@mui/icons-material/Download';
import FileUploadIcon from '@mui/icons-material/FileUpload';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

function TabPanel(props) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`io-tabpanel-${index}`}
      aria-labelledby={`io-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function ImportExportPage() {
  useDocumentTitle("Import / Export");
  const { t } = useTranslation('catalog');
  const { token } = useAuth();
  const { notify } = useNotification();
  const [tabValue, setTabValue] = useState(0);
  
  const [exportProjects, setExportProjects] = useState([]);
  const [importJobs, setImportJobs] = useState([]);
  const [exportJobs, setExportJobs] = useState([]);
  const [tables, setTables] = useState([]);
  const [dataSources, setDataSources] = useState([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [dialogType, setDialogType] = useState(''); // 'export', 'import'
  const [editingProject, setEditingProject] = useState(null);
  const [formData, setFormData] = useState({});
  const [selectedFile, setSelectedFile] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const formats = [
    { value: 'csv', label: t('csv') },
    { value: 'excel', label: t('excel') },
    { value: 'json', label: t('json') },
  ];

  const schedules = [
    { value: 'manual', label: t('manual') },
    { value: 'daily', label: t('daily') },
    { value: 'weekly', label: t('weekly') },
    { value: 'monthly', label: t('monthly') },
  ];

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projects, imports, exports, tbls, sources] = await Promise.all([
        fetchExportProjects(token),
        fetchImportJobs(token),
        fetchExportJobs(token),
        fetchDataSchemaTables(token),
        fetchDataSources(token),
      ]);
      setExportProjects(Array.isArray(projects) ? projects : projects.results || []);
      setImportJobs(Array.isArray(imports) ? imports : imports.results || []);
      setExportJobs(Array.isArray(exports) ? exports : exports.results || []);
      setTables(Array.isArray(tbls) ? tbls : tbls.results || []);
      setDataSources(Array.isArray(sources) ? sources : sources.results || []);
    } catch (err) {
      setError(err.message || t('importExportLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOpenDialog = (type, project = null) => {
    setDialogType(type);
    if (project && type === 'export') {
      setEditingProject(project);
      setFormData({
        name: project.name,
        data_table: project.data_table,
        format: project.format || 'csv',
        schedule: project.schedule || 'manual',
        description: project.description || '',
      });
    } else {
      setEditingProject(null);
      setFormData({ format: 'csv', schedule: 'manual' });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingProject(null);
    setFormData({});
    setSelectedFile(null);
  };

  const handleSave = async () => {
    try {
      if (dialogType === 'export') {
        if (editingProject) {
          await updateExportProject(token, editingProject.id, formData);
        } else {
          await createExportProject(token, formData);
        }
        await loadData();
      }
      handleCloseDialog();
    } catch (err) {
      setError(err.message || t('saveFailed'));
    }
  };

  const handleDelete = async (type, id) => {
    try {
      if (type === 'export') {
        const result = await deleteExportProject(token, id);
        if (result && result.archived) {
          notify({ message: t('exportProjectArchived'), type: 'info' });
          setError(null);
        } else {
          notify({ message: t('exportProjectDeleted'), type: 'success' });
        }
      }
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      setError(err.message || t('deleteFailed'));
      notify({ message: err.message || t('deleteFailed'), type: 'error' });
    }
  };

  const handleRunExport = async (id) => {
    try {
      await runExportProject(token, id);
      notify({ message: t('exportStartedHint'), type: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || t('exportRunFailed'));
      notify({ message: err.message || t('exportRunFailed'), type: 'error' });
    }
  };

  const handleDownloadExport = async (id) => {
    try {
      const result = await getExportJobDownloadUrl(token, id);
      if (result.download_url) {
        window.open(result.download_url, '_blank');
      }
    } catch (err) {
      setError(err.message || t('downloadUrlFailed'));
    }
  };

  const handleUploadFile = async () => {
    if (!selectedFile || !formData.data_table) {
      setError(t('selectFileAndTable'));
      return;
    }
    try {
      await createImportJob(token, {
        data_table: formData.data_table,
        source: formData.source || null,
        file: selectedFile,
        format: formData.format || 'csv',
      });
      notify({ message: t('importJobCreatedHint'), type: 'success' });
      await loadData();
      handleCloseDialog();
    } catch (err) {
      setError(err.message || t('uploadFailed'));
      notify({ message: err.message || t('uploadFailed'), type: 'error' });
    }
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>;
  }

  return (
    <Box sx={{ p: 3 }}>
      <PageHeader
        title={t('importExport')}
        subtitle={t('importExportSubtitle')}
        description={t('importExportDescription')}
      />
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(e, val) => setTabValue(val)}>
          <Tab label={t('exportProjects')} />
          <Tab label={t('importJobs')} />
          <Tab label={t('exportJobs')} />
        </Tabs>
      </Box>

      {/* Export Projects Tab */}
      <TabPanel value={tabValue} index={0}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog('export')}>
            {t('newProject')}
          </Button>
        </Box>
        {exportProjects.length === 0 ? (
          <Alert>{t('noExportProjectsFound')}</Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'background.alt' }}>
                  <TableCell>{t('name')}</TableCell>
                  <TableCell>{t('table')}</TableCell>
                  <TableCell>{t('format')}</TableCell>
                  <TableCell>{t('schedule')}</TableCell>
                  <TableCell align="right">{t('actions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {exportProjects.map((project) => (
                  <TableRow key={project.id} hover>
                    <TableCell sx={{ fontWeight: 500 }}>{project.name}</TableCell>
                    <TableCell>{project.data_table_title || project.data_table}</TableCell>
                    <TableCell>{project.format}</TableCell>
                    <TableCell>{project.schedule}</TableCell>
                    <TableCell align="right">
                      <Tooltip title={t('run')}>
                        <IconButton size="small" onClick={() => handleRunExport(project.id)}>
                          <PlayArrowIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t('common:edit')}>
                        <IconButton size="small" onClick={() => handleOpenDialog('export', project)}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t('common:delete')}>
                        <IconButton size="small" color="error" onClick={() => setDeleteConfirm({ type: 'export', id: project.id, name: project.name })}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </TabPanel>

      {/* Import Jobs Tab */}
      <TabPanel value={tabValue} index={1}>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>{t('uploadDataFile')}</Typography>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <FormControl sx={{ minWidth: 200 }}>
                <InputLabel>{t('targetTable')}</InputLabel>
                <Select
                  value={formData.data_table || ''}
                  onChange={(e) => setFormData({ ...formData, data_table: e.target.value })}
                  label={t('targetTable')}
                >
                  {tables.map((tbl) => (
                    <MenuItem key={tbl.id} value={tbl.id}>{tbl.title}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl sx={{ minWidth: 150 }}>
                <InputLabel>{t('format')}</InputLabel>
                <Select
                  value={formData.format || 'csv'}
                  onChange={(e) => setFormData({ ...formData, format: e.target.value })}
                  label={t('format')}
                >
                  {formats.map((fmt) => (
                    <MenuItem key={fmt.value} value={fmt.value}>{fmt.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl sx={{ minWidth: 150 }}>
                <InputLabel>{t('dataSource')}</InputLabel>
                <Select
                  value={formData.source || ''}
                  onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                  label={t('dataSource')}
                >
                  <MenuItem value="">{t('noneShort')}</MenuItem>
                  {dataSources.map((src) => (
                    <MenuItem key={src.id} value={src.id}>{src.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Input
                type="file"
                onChange={(e) => setSelectedFile(e.target.files[0])}
                sx={{ flex: 1 }}
              />
              <Button
                variant="contained"
                startIcon={<CloudUploadIcon />}
                onClick={handleUploadFile}
              >
                {t('upload')}
              </Button>
            </Box>
          </CardContent>
        </Card>

        {importJobs.length === 0 ? (
          <Alert>{t('noImportJobsFound')}</Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'background.alt' }}>
                  <TableCell>{t('table')}</TableCell>
                  <TableCell>{t('status')}</TableCell>
                  <TableCell>{t('rows')}</TableCell>
                  <TableCell>{t('errors')}</TableCell>
                  <TableCell>{t('created')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {importJobs.map((job) => (
                  <TableRow key={job.id} hover>
                    <TableCell>{job.data_table_title || job.data_table}</TableCell>
                    <TableCell>
                      <Chip
                        label={job.status}
                        color={job.status === 'done' ? 'success' : job.status === 'failed' ? 'error' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>{job.row_count || 0}</TableCell>
                    <TableCell>{job.error_count || 0}</TableCell>
                    <TableCell sx={{ fontSize: '0.85rem' }}>{new Date(job.created_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </TabPanel>

      {/* Export Jobs Tab */}
      <TabPanel value={tabValue} index={2}>
        {exportJobs.length === 0 ? (
          <Alert>{t('noExportJobsFound')}</Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'background.alt' }}>
                  <TableCell>{t('table')}</TableCell>
                  <TableCell>{t('status')}</TableCell>
                  <TableCell>{t('rows')}</TableCell>
                  <TableCell>{t('format')}</TableCell>
                  <TableCell align="right">{t('actions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {exportJobs.map((job) => (
                  <TableRow key={job.id} hover>
                    <TableCell>{job.data_table_title || job.data_table}</TableCell>
                    <TableCell>
                      <Chip
                        label={job.status}
                        color={job.status === 'ready' ? 'success' : job.status === 'failed' ? 'error' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>{job.row_count || 0}</TableCell>
                    <TableCell>{job.format}</TableCell>
                    <TableCell align="right">
                      {job.status === 'ready' && (
                        <Tooltip title={t('download')}>
                          <IconButton
                            size="small"
                            onClick={() => handleDownloadExport(job.id)}
                          >
                            <DownloadIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </TabPanel>

      {/* Create/Edit export project dialog (SystemDialog — design system primitive) */}
      <SystemDialog
        open={openDialog}
        title={editingProject ? t('editExportProject') : t('newExportProject')}
        onClose={handleCloseDialog}
        onCancel={handleCloseDialog}
        cancelLabel={t('common:cancel')}
        width={480}
        height={480}
        minWidth={400}
        minHeight={400}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button onClick={handleSave} variant="contained" size="small">{t('common:save')}</Button>
        }
      >
        <Box px={2} py={1}>
          <TextField
            label={t('name')}
            size="small"
            fullWidth
            value={formData.name || ''}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
            autoFocus
          />
          <FormControl fullWidth margin="normal" size="small">
            <InputLabel>{t('dataTable')}</InputLabel>
            <Select
              value={formData.data_table || ''}
              onChange={(e) => setFormData({ ...formData, data_table: e.target.value })}
              label={t('dataTable')}
            >
              {tables.map((tbl) => (
                <MenuItem key={tbl.id} value={tbl.id}>{tbl.title}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal" size="small">
            <InputLabel>{t('format')}</InputLabel>
            <Select
              value={formData.format || 'csv'}
              onChange={(e) => setFormData({ ...formData, format: e.target.value })}
              label={t('format')}
            >
              {formats.map((fmt) => (
                <MenuItem key={fmt.value} value={fmt.value}>{fmt.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal" size="small">
            <InputLabel>{t('schedule')}</InputLabel>
            <Select
              value={formData.schedule || 'manual'}
              onChange={(e) => setFormData({ ...formData, schedule: e.target.value })}
              label={t('schedule')}
            >
              {schedules.map((sch) => (
                <MenuItem key={sch.value} value={sch.value}>{sch.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label={t('description')}
            size="small"
            fullWidth
            multiline
            rows={2}
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            margin="normal"
          />
        </Box>
      </SystemDialog>

      {/* Delete confirmation (ConfirmDialog — no window.confirm) */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title={t('deleteExportProjectTitle')}
        message={deleteConfirm?.name ? t('deleteProjectArchivedMessage', { name: deleteConfirm.name }) : t('deleteProjectMessage', { name: t('thisProject') })}
        confirmLabel={t('common:delete')}
        destructive
        onConfirm={() => handleDelete(deleteConfirm?.type, deleteConfirm?.id)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Box>
  );
}
