// src/pages/catalog/ConnectionsPage.jsx
// Catalog: Manage data sources and consuming connections (API keys for external systems)

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
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

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
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
  };

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

  const handleDelete = async (type, id) => {
    if (!window.confirm('Are you sure?')) return;
    try {
      if (type === 'datasource') {
        await deleteDataSource(token, id);
      } else {
        await deleteConsumingConnection(token, id);
      }
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to delete');
    }
  };

  const handleTestDataSource = async (id) => {
    try {
      await testDataSource(token, id);
      setError(null);
      alert('Connection test successful!');
    } catch (err) {
      setError(err.message || 'Connection test failed');
    }
  };

  const handleRotateKey = async (id) => {
    if (!window.confirm('Generate new API key? Current key will be invalidated.')) return;
    try {
      const result = await rotateConsumingConnectionKey(token, id);
      alert(`New API Key (copy now, not shown again):\n\n${result.api_key}`);
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
                      <IconButton size="small" color="error" onClick={() => handleDelete('datasource', source.id)}>
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
                      <Button size="small" onClick={() => handleRotateKey(conn.id)}>
                        Rotate
                      </Button>
                    </Tooltip>
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => handleOpenDialog('consuming', conn)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => handleDelete('consuming', conn.id)}>
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

      {/* Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingItem ? 'Edit Connection' : 'New Connection'}
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
          <TextField
            label="Slug"
            fullWidth
            value={formData.slug || ''}
            onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
            margin="normal"
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>{dialogType === 'datasource' ? 'Source Type' : 'System Type'}</InputLabel>
            <Select
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
