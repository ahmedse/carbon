// src/pages/catalog/ImportExportPage.jsx
// Catalog: Manage bulk import/export of data (jobs and reusable export projects)

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
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
  const { token } = useAuth();
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

  const formats = [
    { value: 'csv', label: 'CSV' },
    { value: 'excel', label: 'Excel' },
    { value: 'json', label: 'JSON' },
  ];

  const schedules = [
    { value: 'manual', label: 'Manual' },
    { value: 'daily', label: 'Daily' },
    { value: 'weekly', label: 'Weekly' },
    { value: 'monthly', label: 'Monthly' },
  ];

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
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
      setError(err.message || 'Failed to load import/export data');
    } finally {
      setLoading(false);
    }
  };

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
      setError(err.message || 'Failed to save');
    }
  };

  const handleDelete = async (type, id) => {
    if (!window.confirm('Are you sure?')) return;
    try {
      if (type === 'export') {
        await deleteExportProject(token, id);
      }
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to delete');
    }
  };

  const handleRunExport = async (id) => {
    try {
      await runExportProject(token, id);
      alert('Export started. Check Export Jobs tab for status.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to run export');
    }
  };

  const handleDownloadExport = async (id) => {
    try {
      const result = await getExportJobDownloadUrl(token, id);
      if (result.download_url) {
        window.open(result.download_url, '_blank');
      }
    } catch (err) {
      setError(err.message || 'Failed to get download URL');
    }
  };

  const handleUploadFile = async () => {
    if (!selectedFile || !formData.data_table) {
      setError('Please select a file and table');
      return;
    }
    try {
      await createImportJob(token, {
        data_table: formData.data_table,
        source: formData.source || null,
        file: selectedFile,
        format: formData.format || 'csv',
      });
      alert('Import job created. Check Import Jobs tab for status.');
      await loadData();
      handleCloseDialog();
    } catch (err) {
      setError(err.message || 'Failed to upload file');
    }
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>;
  }

  return (
    <Box sx={{ p: 3 }}>
      <PageHeader
        title="Import / Export"
        subtitle="Bulk data ingestion and scheduled export jobs"
        description="Manage reusable export projects with format, filter, and scheduling options. Import CSV/Excel data into existing tables with validation and error handling."
      />
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(e, val) => setTabValue(val)}>
          <Tab label="Export Projects" />
          <Tab label="Import Jobs" />
          <Tab label="Export Jobs" />
        </Tabs>
      </Box>

      {/* Export Projects Tab */}
      <TabPanel value={tabValue} index={0}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog('export')}>
            New Project
          </Button>
        </Box>
        {exportProjects.length === 0 ? (
          <Alert>No export projects found</Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'background.alt' }}>
                  <TableCell>Name</TableCell>
                  <TableCell>Table</TableCell>
                  <TableCell>Format</TableCell>
                  <TableCell>Schedule</TableCell>
                  <TableCell align="right">Actions</TableCell>
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
                      <Tooltip title="Run">
                        <IconButton size="small" onClick={() => handleRunExport(project.id)}>
                          <PlayArrowIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit">
                        <IconButton size="small" onClick={() => handleOpenDialog('export', project)}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton size="small" color="error" onClick={() => handleDelete('export', project.id)}>
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
            <Typography variant="h6" sx={{ mb: 2 }}>Upload Data File</Typography>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <FormControl sx={{ minWidth: 200 }}>
                <InputLabel>Target Table</InputLabel>
                <Select
                  value={formData.data_table || ''}
                  onChange={(e) => setFormData({ ...formData, data_table: e.target.value })}
                  label="Target Table"
                >
                  {tables.map((tbl) => (
                    <MenuItem key={tbl.id} value={tbl.id}>{tbl.title}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl sx={{ minWidth: 150 }}>
                <InputLabel>Format</InputLabel>
                <Select
                  value={formData.format || 'csv'}
                  onChange={(e) => setFormData({ ...formData, format: e.target.value })}
                  label="Format"
                >
                  {formats.map((fmt) => (
                    <MenuItem key={fmt.value} value={fmt.value}>{fmt.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl sx={{ minWidth: 150 }}>
                <InputLabel>Data Source</InputLabel>
                <Select
                  value={formData.source || ''}
                  onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                  label="Data Source"
                >
                  <MenuItem value="">None</MenuItem>
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
                Upload
              </Button>
            </Box>
          </CardContent>
        </Card>

        {importJobs.length === 0 ? (
          <Alert>No import jobs found</Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'background.alt' }}>
                  <TableCell>Table</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Rows</TableCell>
                  <TableCell>Errors</TableCell>
                  <TableCell>Created</TableCell>
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
          <Alert>No export jobs found</Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'background.alt' }}>
                  <TableCell>Table</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Rows</TableCell>
                  <TableCell>Format</TableCell>
                  <TableCell align="right">Actions</TableCell>
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
                        <Tooltip title="Download">
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

      {/* Dialog for Creating Export Project */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingProject ? 'Edit Export Project' : 'New Export Project'}
        </DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            label="Name"
            fullWidth
            value={formData.name || ''}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
            autoFocus
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Data Table</InputLabel>
            <Select
              value={formData.data_table || ''}
              onChange={(e) => setFormData({ ...formData, data_table: e.target.value })}
              label="Data Table"
            >
              {tables.map((tbl) => (
                <MenuItem key={tbl.id} value={tbl.id}>{tbl.title}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel>Format</InputLabel>
            <Select
              value={formData.format || 'csv'}
              onChange={(e) => setFormData({ ...formData, format: e.target.value })}
              label="Format"
            >
              {formats.map((fmt) => (
                <MenuItem key={fmt.value} value={fmt.value}>{fmt.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel>Schedule</InputLabel>
            <Select
              value={formData.schedule || 'manual'}
              onChange={(e) => setFormData({ ...formData, schedule: e.target.value })}
              label="Schedule"
            >
              {schedules.map((sch) => (
                <MenuItem key={sch.value} value={sch.value}>{sch.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Description"
            fullWidth
            multiline
            rows={2}
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSave} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
