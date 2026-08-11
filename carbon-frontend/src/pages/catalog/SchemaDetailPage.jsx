// src/pages/catalog/SchemaDetailPage.jsx
// Schema Detail: Full view of a single table with fields, metadata, relations
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { isGlobalAdmin } from '../../authz';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import SystemDialog from '../../components/SystemDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import StorageIcon from '@mui/icons-material/Storage';
import { fetchDataSchemaTable, fetchDataSchemaFields, updateDataSchemaTable } from '../../api/dataschema';
import { fetchTableRelations } from '../../api/catalog';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import DQRulesTab from './tabs/DQRulesTab';
import GovernanceTab from './tabs/GovernanceTab';
import AuditHistoryTab from './tabs/AuditHistoryTab';
import SchemaStructureTab from './tabs/SchemaStructureTab';

export default function SchemaDetailPage() {
  useDocumentTitle("Table Schema");
  const { tableId } = useParams();
  const { token, user, availablePerspectives, isGlobalAdminFlag } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [table, setTable] = useState(null);
  const [fields, setFields] = useState([]);
  const [relations, setRelations] = useState([]);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editFormData, setEditFormData] = useState({ title: '', description: '' });
  const [saving, setSaving] = useState(false);

  const isAdmin = isGlobalAdmin(user, availablePerspectives, isGlobalAdminFlag);

  const loadSchemaDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tableData, fieldsData, relationsData] = await Promise.all([
        // Direct detail endpoint — avoids list+find on the paginated tables list
        fetchDataSchemaTable(token, tableId),
        fetchDataSchemaFields(token, tableId, null, null),
        fetchTableRelations(token, { from_table: tableId }).catch(() => []),
      ]);

      if (!tableData || tableData?.detail) {
        setError('Table not found');
        notify({ message: 'Table not found', type: 'error' });
        return;
      }

      setTable(tableData);
      // CB-09: list endpoints are paginated ({results:[...]}) — always unwrap
      setFields(Array.isArray(fieldsData) ? fieldsData : (fieldsData?.results || []));
      setRelations(Array.isArray(relationsData) ? relationsData : (relationsData?.results || []));
    } catch (err) {
      const msg = err.message || 'Failed to load schema detail';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, tableId, notify]);

  useEffect(() => {
    loadSchemaDetail();
  }, [loadSchemaDetail]);

  const handleEditMetadataClick = () => {
    setEditFormData({
      title: table?.title || '',
      description: table?.description || '',
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
        description: editFormData.description,
      });
      await loadSchemaDetail();
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

  const headerComponent = (
    <DetailHeader
      title={table?.title || 'Table'}
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
          {
            label: 'Structure',
            component: () => (
              <SchemaStructureTab
                entityData={detailData}
                tableId={tableId}
                table={table}
                fields={fields}
                onChanged={loadSchemaDetail}
                isAdmin={isAdmin}
                onEditMetadata={handleEditMetadataClick}
              />
            ),
          },
          { label: 'Relations', component: SchemaRelationsTab },
          { label: 'DQ Rules', component: () => <DQRulesTab tableId={tableId} fields={fields} /> },
          { label: 'Governance', component: () => <GovernanceTab tableId={tableId} /> },
          { label: 'Audit History', component: () => <AuditHistoryTab tableId={tableId} /> },
        ]}
        loading={loading}
        error={error}
        onClose={handleClose}
        storageKey="carbonSchemaDetail"
        entityData={detailData}
      />

      <SystemDialog
        open={editDialogOpen}
        title="Edit Table Metadata"
        onClose={() => setEditDialogOpen(false)}
        onCancel={() => setEditDialogOpen(false)}
        cancelLabel="Cancel"
        width={480}
        height={360}
        minWidth={400}
        minHeight={300}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button onClick={handleSaveMetadata} variant="contained" size="small" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        }
      >
        <Box px={2} py={1}>
          <TextField
            fullWidth
            size="small"
            label="Title"
            value={editFormData.title}
            onChange={(event) => setEditFormData((current) => ({ ...current, title: event.target.value }))}
            margin="normal"
            variant="outlined"
          />
          <TextField
            fullWidth
            size="small"
            label="Description"
            value={editFormData.description}
            onChange={(event) => setEditFormData((current) => ({ ...current, description: event.target.value }))}
            margin="normal"
            variant="outlined"
            multiline
            rows={4}
          />
        </Box>
      </SystemDialog>
    </>
  );
}
