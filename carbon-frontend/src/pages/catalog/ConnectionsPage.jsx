// src/pages/catalog/ConnectionsPage.jsx
// Catalog: Manage data sources and consuming connections (API keys for external systems)

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
  fetchDataSources,
  createDataSource,
  updateDataSource,
  deleteDataSource,
  testDataSource,
  fetchConsumingConnections,
  createConsumingConnection,
  updateConsumingConnection,
  deleteConsumingConnection,
  rotateConsumingConnectionKey,
} from '../../api/catalog';
import useDocumentTitle from '../../hooks/useDocumentTitle';

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
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import StorageIcon from '@mui/icons-material/Storage';
import VpnKeyIcon from '@mui/icons-material/VpnKey';

function TabPanel(props) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`conn-tabpanel-${index}`}
      aria-labelledby={`conn-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function ConnectionsPage() {
  useDocumentTitle("Connections");
  const { token } = useAuth();
  const [tabValue, setTabValue] = useState(0);
  
  const [dataSources, setDataSources] = useState([]);
  const [consumingConnections, setConsumingConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [dialogType, setDialogType] = useState(''); // 'datasource' or 'consuming'
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({});
  const [deleteTarget, setDeleteTarget] = useState(null); // { type, id, name }
  const [rotateTarget, setRotateTarget] = useState(null);
  const [newKey, setNewKey] = useState(null);
  const { notify } = useNotification();

  const sourceTypes = [
    { value: 'excel', label: 'Excel' },
    { value: 'database', label: 'Database' },
    { value: 'api', label: 'API' },
    { value: 'iot', label: 'IoT' },
    { value: 'mdm', label: 'MDM System' },
  ];

  const systemTypes = [
    { value: 'pulse', label: 'Pulse' },
    { value: 'powerbi', label: 'Power BI' },
    { value: 'tableau', label: 'Tableau' },
    { value: 'webhook', label: 'Webhook' },
    { value: 'custom', label: 'Custom' },
  ];

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sources, connections] = await Promise.all([
        fetchDataSources(token),
        fetchConsumingConnections(token),
      ]);
      setDataSources(Array.isArray(sources) ? sources : sources.results || []);
      setConsumingConnections(Array.isArray(connections) ? connections : connections.results || []);
    } catch (err) {
      setError(err.message || 'Failed to load connections');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOpenDialog = (type, item = null) => {
    setDialogType(type);
    if (item) {
      setEditingItem(item);
      if (type === 'datasource') {
        setFormData({
          name: item.name,
          slug: item.slug || '',
          source_type: item.source_type || 'api',
          description: item.description || '',
          connection_config: item.connection_config || {},
        });
      } else {
        setFormData({
          name: item.name,
          slug: item.slug || '',
          system_type: item.system_type || 'custom',
          description: item.description || '',
          scopes: item.scopes || [],
          is_active: item.is_active !== undefined ? item.is_active : true,
        });
      }
    } else {
      setEditingItem(null);
      setFormData(type === 'datasource' ? { source_type: 'api', connection_config: {} } : { system_type: 'custom', is_active: true });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingItem(null);
    setFormData({});
  };

  const handleSave = async () => {
    try {
      if (dialogType === 'datasource') {
        if (editingItem) {
          await updateDataSource(token, editingItem.id, formData);
        } else {
          await createDataSource(token, formData);
        }
      } else {
        if (editingItem) {
          await updateConsumingConnection(token, editingItem.id, formData);
        } else {
          await createConsumingConnection(token, formData);
        }
      }
      await loadData();
      handleCloseDialog();
    } catch (err) {
      setError(err.message || 'Failed to save connection');
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const { type, id } = deleteTarget;
    setDeleteTarget(null);
    try {
      if (type === 'datasource') {
        await deleteDataSource(token, id);
      } else {
        await deleteConsumingConnection(token, id);
      }
      notify({ message: 'Deleted', type: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to delete');
    }
  };

  const handleTestDataSource = async (id) => {
    try {
      await testDataSource(token, id);
      setError(null);
      notify({ message: 'Connection test successful', type: 'success' });
    } catch (err) {
      setError(err.message || 'Connection test failed');
    }
  };

  const confirmRotateKey = async () => {
    if (!rotateTarget) return;
    const id = rotateTarget;
    setRotateTarget(null);
    try {
      const result = await rotateConsumingConnectionKey(token, id);
      setNewKey(result.api_key);
      notify({ message: 'New API key generated', type: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to rotate key');
    }
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>;
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ mb: 2 }}>Connections</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(e, val) => setTabValue(val)}>
          <Tab label="Data Sources" icon={<StorageIcon />} iconPosition="start" />
          <Tab label="Consuming Connections" icon={<VpnKeyIcon />} iconPosition="start" />
        </Tabs>
      </Box>

      {/* Data Sources Tab */}
      <TabPanel value={tabValue} index={0}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog('datasource')}>
            New Data Source
          </Button>
        </Box>
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.alt' }}>
                <TableCell>Name</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {dataSources.map((source) => (
                <TableRow key={source.id} hover>
                  <TableCell sx={{ fontWeight: 500 }}>{source.name}</TableCell>
                  <TableCell>{source.source_type}</TableCell>
                  <TableCell>
                    <Chip
                      icon={source.last_test_status === 'success' ? <CheckCircleIcon /> : <ErrorIcon />}
                      label={source.last_test_status === 'success' ? 'Connected' : 'Not Tested'}
                      color={source.last_test_status === 'success' ? 'success' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Test">
                      <Button size="small" onClick={() => handleTestDataSource(source.id)}>
                        Test
                      </Button>
                    </Tooltip>
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => handleOpenDialog('datasource', source)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteTarget({ type: 'datasource', id: source.id, name: source.name })}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Consuming Connections Tab */}
      <TabPanel value={tabValue} index={1}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog('consuming')}>
            New Connection
          </Button>
        </Box>
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.alt' }}>
                <TableCell>Name</TableCell>
                <TableCell>System</TableCell>
                <TableCell>Active</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {consumingConnections.map((conn) => (
                <TableRow key={conn.id} hover>
                  <TableCell sx={{ fontWeight: 500 }}>{conn.name}</TableCell>
                  <TableCell>{conn.system_type}</TableCell>
                  <TableCell>
                    <Chip
                      label={conn.is_active ? 'Active' : 'Inactive'}
                      color={conn.is_active ? 'success' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Rotate Key">
                      <Button size="small" onClick={() => setRotateTarget(conn.id)}>
                        Rotate
                      </Button>
                    </Tooltip>
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => handleOpenDialog('consuming', conn)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteTarget({ type: 'consuming', id: conn.id, name: conn.name })}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </TabPanel>

      {/* Create/Edit dialog (SystemDialog — design system primitive) */}
      <SystemDialog
        open={openDialog}
        title={editingItem ? 'Edit Connection' : 'New Connection'}
        onClose={handleCloseDialog}
        onCancel={handleCloseDialog}
        cancelLabel="Cancel"
        width={480}
        height={420}
        minWidth={400}
        minHeight={340}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button onClick={handleSave} variant="contained" size="small">Save</Button>
        }
      >
        <Box px={2} py={1}>
          <TextField
            label="Name"
            size="small"
            fullWidth
            value={formData.name || ''}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            margin="normal"
            autoFocus
          />
          <TextField
            label="Slug"
            size="small"
            fullWidth
            value={formData.slug || ''}
            onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
            margin="normal"
          />
          <FormControl fullWidth margin="normal" size="small">
            <InputLabel>{dialogType === 'datasource' ? 'Source Type' : 'System Type'}</InputLabel>
            <Select
              size="small"
              value={dialogType === 'datasource' ? (formData.source_type || 'api') : (formData.system_type || 'custom')}
              onChange={(e) => setFormData({ 
                ...formData, 
                [dialogType === 'datasource' ? 'source_type' : 'system_type']: e.target.value 
              })}
              label={dialogType === 'datasource' ? 'Source Type' : 'System Type'}
            >
              {(dialogType === 'datasource' ? sourceTypes : systemTypes).map((type) => (
                <MenuItem key={type.value} value={type.value}>{type.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Description"
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

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete connection?"
        message={`Delete "${deleteTarget?.name || 'this connection'}"? This action cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Rotate key confirmation */}
      <ConfirmDialog
        open={!!rotateTarget}
        title="Generate new API key?"
        message="The current key will be invalidated immediately. Existing integrations using it will stop working until updated."
        confirmLabel="Rotate Key"
        destructive
        onConfirm={confirmRotateKey}
        onCancel={() => setRotateTarget(null)}
      />

      {/* New API key (copy before closing) */}
      <SystemDialog
        open={!!newKey}
        title="New API Key"
        onClose={() => setNewKey(null)}
        onCancel={() => setNewKey(null)}
        cancelLabel="Close"
        showCancel={false}
        width={520}
        height={220}
        minWidth={420}
        minHeight={180}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button
            variant="contained"
            size="small"
            onClick={() => { navigator.clipboard?.writeText(newKey || ''); notify({ message: 'API key copied', type: 'success' }); }}
          >
            Copy Key
          </Button>
        }
      >
        <Box px={2} py={1}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Copy this key now — it will not be shown again.
          </Typography>
          <TextField
            fullWidth
            size="small"
            value={newKey || ''}
            InputProps={{ readOnly: true }}
            inputProps={{ 'aria-label': 'New API key' }}
          />
        </Box>
      </SystemDialog>
    </Box>
  );
}
