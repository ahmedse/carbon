// src/pages/catalog/ExportsDetailPage.jsx
// Exports: Export project CRUD with job history and download
import React, { useEffect, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { API_ROUTES } from '../../config';
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  CircularProgress, Alert, Chip, Paper, Tabs, Tab, MenuItem, Select, FormControl, InputLabel
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import DownloadIcon from '@mui/icons-material/Download';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AssignmentIcon from '@mui/icons-material/Assignment';
import { fetchExportProjects, createExportProject, updateExportProject, deleteExportProject, runExportProject, fetchExportJobs, getExportJobDownloadUrl } from '../../api/catalog';

const EMPTY_FORM = { name: '', format: 'excel', schedule: 'manual', description: '' };
const FORMATS = ['csv', 'excel', 'json'];
const SCHEDULES = ['manual', 'daily', 'weekly', 'monthly'];

function TabPanel(props) {
  const { children, value, index } = props;
  return (
    <div hidden={value !== index}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function ExportsDetailPage() {
  const { token } = useAuth();
  const { notify } = useNotification();

  const [projects, setProjects] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [tabIndex, setTabIndex] = useState(0);
  const [runningId, setRunningId] = useState(null);

  useEffect(() => {
    loadData();
  }, [token]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [projectsData, jobsData] = await Promise.all([
        fetchExportProjects(token),
        fetchExportJobs(token)
      ]);
      setProjects(projectsData || []);
      setJobs(jobsData || []);
    } catch (err) {
      const msg = err.message || 'Failed to load exports';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditingProject(null);
    setFormData(EMPTY_FORM);
    setOpenDialog(true);
  };

  const openEdit = (project) => {
    setEditingProject(project);
    setFormData({
      name: project.name,
      format: project.format || 'excel',
      schedule: project.schedule || 'manual',
      description: project.description || ''
    });
    setOpenDialog(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      notify({ message: 'Name is required', type: 'error' });
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (editingProject) {
        await updateExportProject(token, editingProject.id, formData);
        notify({ message: 'Export project updated', type: 'success' });
      } else {
        await createExportProject(token, formData);
        notify({ message: 'Export project created', type: 'success' });
      }
      setOpenDialog(false);
      loadData();
    } catch (err) {
      const msg = err.message || 'Save failed';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (project) => {
    if (!window.confirm(`Delete export project "${project.name}"?`)) return;
    try {
      await deleteExportProject(token, project.id);
      notify({ message: 'Export project deleted', type: 'success' });
      loadData();
    } catch (err) {
      setError(err.message || 'Delete failed');
      notify({ message: err.message || 'Delete failed', type: 'error' });
    }
  };

  const handleRun = async (projectId) => {
    setRunningId(projectId);
    try {
      await runExportProject(token, projectId);
      notify({ message: 'Export started', type: 'success' });
      loadData();
    } catch (err) {
      notify({ message: `Export failed: ${err.message}`, type: 'error' });
    } finally {
      setRunningId(null);
    }
  };

  const handleDownload = async (jobId) => {
    try {
      const res = await getExportJobDownloadUrl(token, jobId);
      const url = res.download_url || `${API_ROUTES.exportJobs}${jobId}/download/`;
      window.open(url, '_blank');
      notify({ message: 'Download started', type: 'success' });
    } catch (err) {
      notify({ message: `Download failed: ${err.message}`, type: 'error' });
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <AssignmentIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
        <Box>
          <Typography variant="h5" fontWeight={700}>Exports</Typography>
          <Typography variant="body2" color="text.secondary">Data export projects and jobs</Typography>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper>
        <Tabs value={tabIndex} onChange={(e, v) => setTabIndex(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Projects" />
          <Tab label="Jobs" />
        </Tabs>

        {/* Projects Tab */}
        <TabPanel value={tabIndex} index={0}>
          <Box sx={{ mb: 2 }}>
            <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
              New Project
            </Button>
          </Box>
          <Table>
            <TableHead>
              <TableRow sx={{ backgroundColor: 'action.hover' }}>
                <TableCell fontWeight={600}>Name</TableCell>
                <TableCell fontWeight={600}>Format</TableCell>
                <TableCell fontWeight={600}>Schedule</TableCell>
                <TableCell fontWeight={600} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {projects.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ py: 3 }}>
                    <Typography color="text.secondary">No export projects</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                projects.map(project => (
                  <TableRow key={project.id} hover>
                    <TableCell fontWeight={500}>{project.name}</TableCell>
                    <TableCell><Chip label={project.format} size="small" variant="outlined" /></TableCell>
                    <TableCell><Chip label={project.schedule} size="small" color="primary" variant="outlined" /></TableCell>
                    <TableCell align="right">
                      <Button
                        size="small"
                        startIcon={<PlayArrowIcon />}
                        onClick={() => handleRun(project.id)}
                        disabled={runningId === project.id}
                        sx={{ mr: 1 }}
                      >
                        {runningId === project.id ? 'Running' : 'Run'}
                      </Button>
                      <IconButton size="small" onClick={() => openEdit(project)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => handleDelete(project)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TabPanel>

        {/* Jobs Tab */}
        <TabPanel value={tabIndex} index={1}>
          <Table>
            <TableHead>
              <TableRow sx={{ backgroundColor: 'action.hover' }}>
                <TableCell fontWeight={600}>Project</TableCell>
                <TableCell fontWeight={600}>Status</TableCell>
                <TableCell fontWeight={600}>Rows</TableCell>
                <TableCell fontWeight={600}>Date</TableCell>
                <TableCell fontWeight={600} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {jobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                    <Typography color="text.secondary">No export jobs</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                jobs.map(job => (
                  <TableRow key={job.id} hover>
                    <TableCell>{job.export_project_name || '—'}</TableCell>
                    <TableCell>
                      <Chip
                        label={job.status}
                        size="small"
                        color={job.status === 'ready' ? 'success' : 'default'}
                        variant={job.status === 'ready' ? 'filled' : 'outlined'}
                      />
                    </TableCell>
                    <TableCell>{job.row_count || 0}</TableCell>
                    <TableCell>
                      <Typography variant="caption">
                        {job.created_at ? new Date(job.created_at).toLocaleDateString() : '—'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      {job.status === 'ready' && (
                        <Button
                          size="small"
                          startIcon={<DownloadIcon />}
                          onClick={() => handleDownload(job.id)}
                        >
                          Download
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TabPanel>
      </Paper>

      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingProject ? 'Edit Export Project' : 'New Export Project'}</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Format</InputLabel>
            <Select
              value={formData.format}
              label="Format"
              onChange={(e) => setFormData({ ...formData, format: e.target.value })}
            >
              {FORMATS.map(f => <MenuItem key={f} value={f}>{f}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel>Schedule</InputLabel>
            <Select
              value={formData.schedule}
              label="Schedule"
              onChange={(e) => setFormData({ ...formData, schedule: e.target.value })}
            >
              {SCHEDULES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField
            fullWidth
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            margin="normal"
            multiline
            rows={3}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSave} variant="contained" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
