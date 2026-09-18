// src/pages/catalog/ConnectionsPage.jsx
// Catalog: Manage data sources and consuming connections (API keys for external systems)

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
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
import { SearchSelect } from '../../components/Form';

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
  const { t } = useTranslation('catalog');
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
    { value: 'excel', label: t('excel') },
    { value: 'database', label: t('database') },
    { value: 'api', label: t('api') },
    { value: 'iot', label: t('iot') },
    { value: 'mdm', label: t('mdmSystem') },
  ];

  const systemTypes = [
    { value: 'pulse', label: t('pulse') },
    { value: 'powerbi', label: t('powerBi') },
    { value: 'tableau', label: t('tableau') },
    { value: 'webhook', label: t('webhook') },
    { value: 'custom', label: t('custom') },
  ];

  const connectionConfigFieldSets = {
    database: [
      { key: 'host', label: t('host') },
      { key: 'port', label: t('port') },
      { key: 'database_name', label: t('databaseName') },
      { key: 'username', label: t('username') },
      { key: 'password', label: t('password'), type: 'password' },
    ],
    api: [
      { key: 'base_url', label: t('baseUrl') },
      { key: 'api_key', label: t('apiKey'), type: 'password' },
    ],
    mdm: [
      { key: 'base_url', label: t('baseUrl') },
      { key: 'api_key', label: t('apiKey'), type: 'password' },
    ],
    iot: [
      { key: 'endpoint', label: t('endpoint') },
      { key: 'api_key', label: t('apiKey'), type: 'password' },
    ],
    excel: [{ key: 'file_path', label: t('filePath') }],
    manual: [{ key: 'file_path', label: t('filePath') }],
  };

  const getConfigFields = (sourceType) =>
    connectionConfigFieldSets[sourceType] || [{ key: 'endpoint', label: t('endpoint') }];

  const setConnectionConfig = (key, value) => {
    setFormData((prev) => ({
      ...prev,
      connection_config: { ...(prev.connection_config || {}), [key]: value },
    }));
  };

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
      setError(err.message || t('connectionsLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

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
          // Do NOT prefill masked secrets (values === '***') into the dialog.
          // Fields render empty; only keys the user actually types are sent.
          connection_config: {},
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
        // Send only config keys the user actually typed (drop empty/unset values).
        // On edit this preserves stored secrets — the backend keeps masked fields
        // untouched when a key is absent.
        const connection_config = Object.entries(formData.connection_config || {})
          .filter(([, value]) => value !== undefined && value !== null && value !== '')
          .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});
        const payload = { ...formData, connection_config };
        if (editingItem) {
          await updateDataSource(token, editingItem.id, payload);
        } else {
          await createDataSource(token, payload);
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
      setError(err.message || t('connectionSaveFailed'));
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
      notify({ message: t('deleted'), type: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || t('deleteFailed'));
    }
  };

  const handleTestDataSource = async (id) => {
    try {
      await testDataSource(token, id);
      setError(null);
      notify({ message: t('connectionTestSuccess'), type: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || t('connectionTestFailedShort'));
    }
  };

  const confirmRotateKey = async () => {
    if (!rotateTarget) return;
    const id = rotateTarget;
    setRotateTarget(null);
    try {
      const result = await rotateConsumingConnectionKey(token, id);
      setNewKey(result.api_key);
      notify({ message: t('newApiKeyGenerated'), type: 'success' });
      await loadData();
    } catch (err) {
      setError(err.message || t('rotateKeyFailed'));
    }
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>;
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ mb: 2 }}>{t('connections')}</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(e, val) => setTabValue(val)}>
          <Tab label={t('dataSources')} icon={<StorageIcon />} iconPosition="start" />
          <Tab label={t('consumingConnections')} icon={<VpnKeyIcon />} iconPosition="start" />
        </Tabs>
      </Box>

      {/* Data Sources Tab */}
      <TabPanel value={tabValue} index={0}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button startIcon={<AddIcon />} variant="contained" onClick={() => handleOpenDialog('datasource')}>
            {t('newDataSource')}
          </Button>
        </Box>
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.alt' }}>
                <TableCell>{t('name')}</TableCell>
                <TableCell>{t('type')}</TableCell>
                <TableCell>{t('status')}</TableCell>
                <TableCell align="right">{t('actions')}</TableCell>
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
                      label={source.last_test_status === 'success' ? t('connected') : t('notTested')}
                      color={source.last_test_status === 'success' ? 'success' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title={t('test')}>
                      <Button size="small" onClick={() => handleTestDataSource(source.id)}>
                        {t('test')}
                      </Button>
                    </Tooltip>
                    <Tooltip title={t('common:edit')}>
                      <IconButton size="small" onClick={() => handleOpenDialog('datasource', source)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('common:delete')}>
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
            {t('newConnection')}
          </Button>
        </Box>
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'background.alt' }}>
                <TableCell>{t('name')}</TableCell>
                <TableCell>{t('system')}</TableCell>
                <TableCell>{t('active')}</TableCell>
                <TableCell align="right">{t('actions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {consumingConnections.map((conn) => (
                <TableRow key={conn.id} hover>
                  <TableCell sx={{ fontWeight: 500 }}>{conn.name}</TableCell>
                  <TableCell>{conn.system_type}</TableCell>
                  <TableCell>
                    <Chip
                      label={conn.is_active ? t('active') : t('inactive')}
                      color={conn.is_active ? 'success' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title={t('rotateKey')}>
                      <Button size="small" onClick={() => setRotateTarget(conn.id)}>
                        {t('rotate')}
                      </Button>
                    </Tooltip>
                    <Tooltip title={t('common:edit')}>
                      <IconButton size="small" onClick={() => handleOpenDialog('consuming', conn)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t('common:delete')}>
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
        title={editingItem ? t('editConnection') : t('newConnection')}
        onClose={handleCloseDialog}
        onCancel={handleCloseDialog}
        cancelLabel={t('common:cancel')}
        width={480}
        height={640}
        minWidth={400}
        minHeight={480}
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
          <TextField
            label={t('slug')}
            size="small"
            fullWidth
            value={formData.slug || ''}
            onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
            margin="normal"
          />
          <SearchSelect
            options={dialogType === 'datasource' ? sourceTypes : systemTypes}
            valueKey="value"
            labelKey="label"
            label={dialogType === 'datasource' ? t('sourceType') : t('systemType')}
            value={dialogType === 'datasource' ? (formData.source_type || 'api') : (formData.system_type || 'custom')}
            onChange={(v) => setFormData({
              ...formData,
              [dialogType === 'datasource' ? 'source_type' : 'system_type']: v?.value ?? '',
            })}
            clearable={false}
          />
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
          {dialogType === 'datasource' &&
            getConfigFields(formData.source_type).map((field) => (
              <TextField
                key={field.key}
                label={field.label}
                size="small"
                fullWidth
                type={field.type || 'text'}
                value={(formData.connection_config || {})[field.key] || ''}
                onChange={(e) => setConnectionConfig(field.key, e.target.value)}
                placeholder={editingItem ? t('unchangedHint') : undefined}
                margin="normal"
              />
            ))}
        </Box>
      </SystemDialog>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title={t('deleteConnectionTitle')}
        message={t('deleteConnectionMessage', { name: deleteTarget?.name || t('thisConnection') })}
        confirmLabel={t('common:delete')}
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Rotate key confirmation */}
      <ConfirmDialog
        open={!!rotateTarget}
        title={t('generateApiKeyTitle')}
        message={t('generateApiKeyMessage')}
        confirmLabel={t('rotateKeyConfirm')}
        destructive
        onConfirm={confirmRotateKey}
        onCancel={() => setRotateTarget(null)}
      />

      {/* New API key (copy before closing) */}
      <SystemDialog
        open={!!newKey}
        title={t('newApiKey')}
        onClose={() => setNewKey(null)}
        onCancel={() => setNewKey(null)}
        cancelLabel={t('common:close')}
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
            onClick={() => { navigator.clipboard?.writeText(newKey || ''); notify({ message: t('apiKeyCopied'), type: 'success' }); }}
          >
            {t('copyKey')}
          </Button>
        }
      >
        <Box px={2} py={1}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {t('copyKeyHint')}
          </Typography>
          <TextField
            fullWidth
            size="small"
            value={newKey || ''}
            InputProps={{ readOnly: true }}
            inputProps={{ 'aria-label': t('newApiKey') }}
          />
        </Box>
      </SystemDialog>
    </Box>
  );
}
