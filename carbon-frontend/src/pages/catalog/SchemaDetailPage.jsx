// src/pages/catalog/SchemaDetailPage.jsx
// Schema Detail: Full view of a single table with fields, metadata, relations
import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import StorageIcon from '@mui/icons-material/Storage';
import { fetchDataSchemaTables, fetchDataSchemaFields, updateDataSchemaTable } from '../../api/dataschema';
import { fetchTableRelations } from '../../api/catalog';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';

export default function SchemaDetailPage() {
  const { tableId } = useParams();
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [table, setTable] = useState(null);
  const [fields, setFields] = useState([]);
  const [relations, setRelations] = useState([]);
  const [tabIndex, setTabIndex] = useState(0);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editFormData, setEditFormData] = useState({ title: '', description: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSchemaDetail();
  }, [tableId, token]);

  const loadSchemaDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const [tableData, fieldsData, relationsData] = await Promise.all([
        fetchDataSchemaTables(token, null, null).then(tables => tables.find(t => t.id === parseInt(tableId))),
        fetchDataSchemaFields(token, tableId, null, null),
        fetchTableRelations(token, { from_table: tableId }).catch(() => []),
      ]);

      if (!tableData) {
        setError('Table not found');
        notify({ message: 'Table not found', type: 'error' });
        return;
      }

      setTable(tableData);
      setFields(fieldsData || []);
      setRelations(relationsData || []);
    } catch (err) {
      const msg = err.message || 'Failed to load schema detail';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleEditMetadataClick = () => {
    setEditFormData({
      title: table.title || '',
      description: table.description || ''
    });
    setEditDialogOpen(true);
  };

  const handleClose = () => {
    navigate(-1);
  };

  const handleSaveMetadata = async () => {
    setSaving(true);
    try {
      await updateDataSchemaTable(token, tableId, {
        title: editFormData.title,
        description: editFormData.description
      });
      setTable({ ...table, ...editFormData });
      setEditDialogOpen(false);
      notify({ message: 'Metadata updated successfully', type: 'success' });
    } catch (err) {
      const msg = err.message || 'Failed to update metadata';
      notify({ message: msg, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const detailData = useMemo(() => ({ table, fields, relations }), [table, fields, relations]);

  const SchemaOverviewTab = ({ entityData }) => (
    <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Button variant="outlined" onClick={handleEditMetadataClick} sx={{ alignSelf: 'flex-start' }}>
        Edit Metadata
      </Button>
      {entityData?.fields?.length === 0 ? (
        <Typography color="text.secondary">No fields defined</Typography>
      ) : (
        <Paper variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: 'action.hover' }}>
                <TableCell fontWeight={600}>Name</TableCell>
                <TableCell fontWeight={600}>Type</TableCell>
                <TableCell fontWeight={600}>Required</TableCell>
                <TableCell fontWeight={600}>Description</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entityData?.fields?.map((field) => (
                <TableRow key={field.id}>
                  <TableCell>{field.name}</TableCell>
                  <TableCell>
                    <Chip label={field.field_type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>{field.required ? 'Yes' : 'No'}</TableCell>
                  <TableCell>{field.description || '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
    </Box>
  );

  const SchemaRelationsTab = ({ entityData }) => (
    <Box sx={{ p: 3 }}>
      {entityData?.relations?.length === 0 ? (
        <Typography color="text.secondary">No relations defined</Typography>
      ) : (
        <Paper variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: 'action.hover' }}>
                <TableCell fontWeight={600}>From Table</TableCell>
                <TableCell fontWeight={600}>To Table</TableCell>
                <TableCell fontWeight={600}>Type</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entityData?.relations?.map((rel) => (
                <TableRow key={rel.id}>
                  <TableCell>{rel.from_table_title}</TableCell>
                  <TableCell>{rel.to_table_title}</TableCell>
                  <TableCell>
                    <Chip label={rel.relation_type} size="small" color="primary" variant="outlined" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
    </Box>
  );

  const SchemaSummaryMetrics = ({ entityData }) => (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'grid', gap: 1.5 }}>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Fields</Typography>
          <Typography variant="h6">{entityData?.fields?.length || 0}</Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Incoming Relations</Typography>
          <Typography variant="h6">{(entityData?.relations || []).filter((r) => r.to_table === parseInt(tableId)).length}</Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Outgoing Relations</Typography>
          <Typography variant="h6">{(entityData?.relations || []).filter((r) => r.from_table === parseInt(tableId)).length}</Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Last Modified</Typography>
          <Typography variant="h6">{table?.updated_at ? new Date(table.updated_at).toLocaleDateString() : 'N/A'}</Typography>
        </Paper>
      </Box>
    </Box>
  );

  const headerComponent = (
    <DetailHeader
      breadcrumbs={[
        { label: 'Home', icon: <HomeIcon />, path: '/' },
        { label: 'Catalog', path: '/catalog' },
        { label: 'Schemas', path: '/catalog/schemas' },
      ]}
      title={table?.title || 'Schema'}
      description={table?.description || 'Table definition and relationships'}
      icon={StorageIcon}
      onClose={handleClose}
    />
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!table) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error || 'Table not found'}</Alert>
      </Box>
    );
  }

  return (
    <>
      <BaseDetailPage
        headerComponent={headerComponent}
        mainTabs={[
          { label: 'Overview', component: SchemaOverviewTab },
          { label: 'Relations', component: SchemaRelationsTab },
        ]}
        metricsTabs={[{ label: 'Summary', component: SchemaSummaryMetrics }]}
        loading={loading}
        error={error}
        onClose={handleClose}
        storageKey="carbonSchemaDetail"
        entityData={detailData}
      />

      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Table Metadata</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Title"
            value={editFormData.title}
            onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
            margin="normal"
            variant="outlined"
          />
          <TextField
            fullWidth
            label="Description"
            value={editFormData.description}
            onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
            margin="normal"
            variant="outlined"
            multiline
            rows={4}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSaveMetadata} variant="contained" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
