// src/pages/admin/catalog/FieldPoliciesPanel.jsx
// Field Access Policies — column-level RBAC (deny/mask) + masking strategies (EPH-4A/4B).
// Admin shell: PageContainer + PageHeader + StandardDataGrid + SystemDialog + ConfirmDialog.
// Theme tokens only (RULE_8); API via apiFetch wrappers (RULE_10); admin copy is plain English.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import LockIcon from '@mui/icons-material/Lock';
import RefreshIcon from '@mui/icons-material/Refresh';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import StandardDataGrid from '../../../components/StandardDataGrid';
import SystemDialog from '../../../components/SystemDialog';
import ConfirmDialog from '../../../components/ConfirmDialog';
import { fetchDataSchemaTables } from '../../../api/dataschema';
import {
  createFieldPolicy,
  deleteFieldPolicy,
  fetchAllFields,
  getFieldPolicies,
  updateFieldMaskingStrategy,
} from '../../../api/fieldPolicies';

const MASKING_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'redact', label: 'Redact' },
  { value: 'hash', label: 'Hash' },
  { value: 'truncate', label: 'Truncate' },
  { value: 'null', label: 'Null' },
];

function MaskingChip({ value }) {
  const label = MASKING_OPTIONS.find((o) => o.value === value)?.label || value || 'None';
  return <Chip label={label} size="small" variant="outlined" />;
}

function ActionChip({ value }) {
  const color = value === 'deny' ? 'error' : value === 'mask' ? 'warning' : undefined;
  const label = value === 'deny' ? 'Deny' : value === 'mask' ? 'Mask' : value || '—';
  return <Chip label={label} size="small" variant="filled" color={color} />;
}

export default function FieldPoliciesPanel() {
  useDocumentTitle('Field Access Policies');
  const { token, context } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [fields, setFields] = useState([]);
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');

  const [selectedField, setSelectedField] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [policiesLoading, setPoliciesLoading] = useState(false);

  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ required_capability: '', action: 'deny' });
  const [saving, setSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState(null);

  const projectId = context?.project_id || null;
  const moduleId = context?.module_id || null;

  const loadFields = useCallback(async () => {
    try {
      setLoading(true);
      const [fieldsData, tablesData] = await Promise.all([
        fetchAllFields(token, projectId, moduleId),
        fetchDataSchemaTables(token, projectId, moduleId),
      ]);
      setFields(Array.isArray(fieldsData) ? fieldsData : fieldsData?.results || []);
      setTables(Array.isArray(tablesData) ? tablesData : tablesData?.results || []);
    } catch (err) {
      notifyFromError(err, 'Failed to load fields');
      setFields([]);
      setTables([]);
    } finally {
      setLoading(false);
    }
  }, [token, projectId, moduleId, notifyFromError]);

  useEffect(() => {
    loadFields();
  }, [loadFields]);

  // Debounced client-side field search
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput.trim().toLowerCase()), 300);
    return () => clearTimeout(id);
  }, [searchInput, setSearch]);

  const tableNames = useMemo(() => {
    const map = {};
    tables.forEach((t) => {
      map[t.id] = t.title || t.name || `Table #${t.id}`;
    });
    return map;
  }, [tables]);

  const filteredFields = useMemo(() => {
    if (!search) return fields;
    return fields.filter(
      (f) =>
        (f.name || '').toLowerCase().includes(search) ||
        (f.label || '').toLowerCase().includes(search) ||
        (f.type || '').toLowerCase().includes(search)
    );
  }, [fields, search]);

  const loadPolicies = useCallback(
    async (fieldId) => {
      setPoliciesLoading(true);
      try {
        const data = await getFieldPolicies(token, fieldId);
        setPolicies(Array.isArray(data) ? data : data?.results || []);
      } catch (err) {
        notifyFromError(err, 'Failed to load field policies');
        setPolicies([]);
      } finally {
        setPoliciesLoading(false);
      }
    },
    [token, notifyFromError]
  );

  const handleSelectField = (field) => {
    setSelectedField(field);
    loadPolicies(field.id);
  };

  const handleMaskingChange = async (strategy) => {
    if (!selectedField) return;
    const previous = selectedField.masking_strategy || 'none';
    setSelectedField((f) => ({ ...f, masking_strategy: strategy }));
    try {
      await updateFieldMaskingStrategy(token, selectedField.id, strategy);
      notify({ message: 'Masking strategy updated', type: 'success' });
      await loadFields();
    } catch (err) {
      notifyFromError(err, 'Failed to update masking strategy');
      setSelectedField((f) => ({ ...f, masking_strategy: previous }));
    }
  };

  const handleAddPolicy = async () => {
    if (!selectedField || !form.required_capability.trim()) return;
    setSaving(true);
    try {
      await createFieldPolicy(token, selectedField.id, {
        required_capability: form.required_capability.trim(),
        action: form.action,
      });
      notify({ message: 'Policy added', type: 'success' });
      setAddOpen(false);
      setForm({ required_capability: '', action: 'deny' });
      await loadPolicies(selectedField.id);
    } catch (err) {
      notifyFromError(err, 'Failed to add policy');
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePolicy = async () => {
    if (!deleteTarget || !selectedField) return;
    try {
      await deleteFieldPolicy(token, selectedField.id, deleteTarget.id);
      notify({ message: 'Policy deleted', type: 'success' });
      setDeleteTarget(null);
      await loadPolicies(selectedField.id);
    } catch (err) {
      notifyFromError(err, 'Failed to delete policy');
    }
  };

  const handleRefresh = () => {
    loadFields();
    if (selectedField) loadPolicies(selectedField.id);
  };

  const fmtDate = (d) => {
    if (!d) return '—';
    try {
      return new Date(d).toLocaleDateString();
    } catch {
      return '—';
    }
  };

  const columns = useMemo(
    () => [
      { field: 'id', headerName: 'ID', width: 70 },
      { field: 'name', headerName: 'Field', flex: 1, minWidth: 150 },
      {
        field: 'label',
        headerName: 'Label',
        flex: 1,
        minWidth: 130,
        valueGetter: (value, row) => row.label || row.name || '—',
      },
      {
        field: 'table',
        headerName: 'Table',
        flex: 1,
        minWidth: 140,
        valueGetter: (value, row) => tableNames[row.data_table] || `Table #${row.data_table}`,
      },
      { field: 'type', headerName: 'Type', width: 100 },
      {
        field: 'masking_strategy',
        headerName: 'Masking',
        width: 120,
        renderCell: (params) => <MaskingChip value={params.value} />,
      },
    ],
    [tableNames]
  );

  return (
    <PageContainer>
      <PageHeader
        title="Field Access Policies"
        description="Column-level access control and masking for sensitive fields. Restrict which capabilities can view a field, hide PII values with a masking strategy, and review the policies applied to each field."
        actions={
          <IconButton size="small" onClick={handleRefresh} aria-label="Refresh field policies">
            <RefreshIcon />
          </IconButton>
        }
      />

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ flex: 1, minHeight: 0 }}>
        {/* Field list */}
        <Box sx={{ width: { xs: '100%', md: 460 }, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <TextField
            label="Search fields"
            placeholder="Search by field or label…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            size="small"
            fullWidth
            sx={{ mb: 1 }}
          />
          <StandardDataGrid
            rows={filteredFields}
            columns={columns}
            loading={loading}
            pageSize={25}
            toolbar
            onRowClick={(params) => handleSelectField(params.row)}
            sx={{ flex: 1, minHeight: 360, maxHeight: 'calc(100vh - 220px)' }}
          />
        </Box>

        {/* Selected field detail */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {selectedField ? (
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent>
                <Stack spacing={2}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1 }}>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>
                        {selectedField.label || selectedField.name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {selectedField.name} · {selectedField.type || 'string'} ·{' '}
                        {tableNames[selectedField.data_table] || `Table #${selectedField.data_table}`}
                      </Typography>
                    </Box>
                    <Chip
                      icon={<LockIcon sx={{ color: 'primary.main' }} />}
                      label={`Field #${selectedField.id}`}
                      size="small"
                      variant="outlined"
                    />
                  </Box>

                  {/* Masking strategy */}
                  <Box>
                    <Typography sx={{ fontSize: '0.6875rem', fontWeight: 600, mb: 0.5 }}>Masking Strategy</Typography>
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ xs: 'flex-start', sm: 'center' }}>
                      <Select
                        value={selectedField.masking_strategy || 'none'}
                        onChange={(e) => handleMaskingChange(e.target.value)}
                        size="small"
                        variant="outlined"
                        sx={{ minWidth: 140 }}
                      >
                        {MASKING_OPTIONS.map((o) => (
                          <MenuItem key={o.value} value={o.value}>
                            {o.label}
                          </MenuItem>
                        ))}
                      </Select>
                      <Typography variant="caption" color="text.secondary">
                        How values appear to users without the required capability.
                      </Typography>
                    </Stack>
                  </Box>

                  {/* Policies */}
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography sx={{ fontSize: '0.6875rem', fontWeight: 600 }}>Access Policies</Typography>
                    <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
                      Add Policy
                    </Button>
                  </Box>

                  {policiesLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                      <CircularProgress size={24} />
                    </Box>
                  ) : policies.length === 0 ? (
                    <Alert severity="info">
                      No access policies for this field. Add one to deny or mask it for users without the required
                      capability.
                    </Alert>
                  ) : (
                    <Paper variant="outlined">
                      <Table size="small">
                        <TableHead>
                          <TableRow sx={{ bgcolor: 'action.hover' }}>
                            <TableCell sx={{ fontWeight: 600 }}>Required Capability</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Created By</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Created At</TableCell>
                            <TableCell />
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {policies.map((policy) => (
                            <TableRow key={policy.id} hover>
                              <TableCell>
                                <Chip label={policy.required_capability} size="small" variant="outlined" />
                              </TableCell>
                              <TableCell>
                                <ActionChip value={policy.action} />
                              </TableCell>
                              <TableCell>{policy.created_by || '—'}</TableCell>
                              <TableCell>{fmtDate(policy.created_at)}</TableCell>
                              <TableCell align="right">
                                <Tooltip title="Delete policy">
                                  <IconButton
                                    size="small"
                                    sx={{ color: 'error.main' }}
                                    onClick={() => setDeleteTarget(policy)}
                                    aria-label="Delete policy"
                                  >
                                    <DeleteIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </Paper>
                  )}
                </Stack>
              </CardContent>
            </Card>
          ) : (
            <Paper
              variant="outlined"
              sx={{ p: 3, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 360 }}
            >
              <Typography variant="body2" color="text.secondary">
                Select a field to view its access policies
              </Typography>
            </Paper>
          )}
        </Box>
      </Stack>

      {/* Add policy dialog */}
      <SystemDialog
        open={addOpen}
        title="Add Field Policy"
        onClose={() => setAddOpen(false)}
        onCancel={() => setAddOpen(false)}
        cancelLabel="Cancel"
        actions={
          <Button
            variant="contained"
            size="small"
            onClick={handleAddPolicy}
            disabled={saving || !form.required_capability.trim()}
          >
            {saving ? 'Adding…' : 'Add Policy'}
          </Button>
        }
        width={480}
        height={400}
        minWidth={400}
        minHeight={320}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
      >
        <Box px={2} py={1}>
          <Stack spacing={2}>
            <Typography variant="body2" color="text.secondary">
              Users without the selected capability will be{' '}
              {form.action === 'deny' ? 'blocked from viewing' : 'shown masked values for'} this field.
            </Typography>
            <TextField
              label="Required Capability"
              placeholder="catalog:view_pii"
              value={form.required_capability}
              onChange={(e) => setForm((p) => ({ ...p, required_capability: e.target.value }))}
              fullWidth
              size="small"
              required
              helperText="Capability users must hold to see this field unmasked (e.g. catalog:view_pii)"
            />
            <TextField
              label="Action"
              select
              value={form.action}
              onChange={(e) => setForm((p) => ({ ...p, action: e.target.value }))}
              fullWidth
              size="small"
            >
              <MenuItem value="deny">Deny</MenuItem>
              <MenuItem value="mask">Mask</MenuItem>
            </TextField>
          </Stack>
        </Box>
      </SystemDialog>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Policy?"
        message={
          deleteTarget
            ? `Remove the "${deleteTarget.required_capability}" policy from this field? Users without this capability will regain full access to the field.`
            : ''
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeletePolicy}
        onCancel={() => setDeleteTarget(null)}
      />
    </PageContainer>
  );
}
