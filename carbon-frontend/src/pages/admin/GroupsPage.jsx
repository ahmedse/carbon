import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, IconButton, TextField, Tooltip, Typography } from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import EditRounded from '@mui/icons-material/EditRounded';
import DeleteRounded from '@mui/icons-material/DeleteRounded';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import { useNavigate } from 'react-router-dom';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import { useAuth } from '../../auth/AuthContext';
import { apiFetch } from '../../api/api';
import { BRAND_DUTIES, PLATFORM_NAME } from '../../config/branding';

const EMPTY_FORM = { name: '', description: '' };

const BRAND_DUTY_IDS = new Set(BRAND_DUTIES.map((d) => d.id));
const APP_BY_DUTY = Object.fromEntries(BRAND_DUTIES.map((d) => [d.id, d.app]));

function rowDuty(group) {
  return group.duty || group.name || '';
}

function dutyKind(group) {
  const duty = rowDuty(group);
  if (BRAND_DUTY_IDS.has(duty)) return 'brand';
  if (!duty.includes(':')) return 'other';
  const prefix = duty.split(':')[0];
  if (prefix === 'platform') return 'platform';
  return 'other';
}

const EMPTY_FILTERS = { domain: '', role_type: '', kind: '' };

export default function GroupsPage() {
  useDocumentTitle('Duties');
  const { user } = useAuth();
  const token = user?.token;
  const navigate = useNavigate();
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({
    ...EMPTY_FILTERS,
    kind: BRAND_DUTY_IDS.size ? 'brand' : '',
  });
  const [highlightRow, setHighlightRow] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiFetch('accounts/groups/', { method: 'GET', token });
      setGroups(Array.isArray(data) ? data : data.results || []);
    } catch (e) {
      setError(e.message || 'Failed to load duties');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditingId(null); setForm(EMPTY_FORM); setDialogOpen(true); };
  const openEdit = (group) => {
    setEditingId(group.id);
    setForm({ name: group.name, description: group.description || '' });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { setError('Stored group name is required.'); return; }
    setSaving(true);
    setError('');
    try {
      const body = { name: form.name.trim(), description: form.description };
      await apiFetch(editingId ? `accounts/groups/${editingId}/` : 'accounts/groups/', {
        method: editingId ? 'PUT' : 'POST',
        token,
        body,
      });
      setDialogOpen(false);
      load();
    } catch (e) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setError('');
    try {
      await apiFetch(`accounts/groups/${deleteTarget.id}/`, { method: 'DELETE', token });
      setDeleteTarget(null);
      load();
    } catch (e) {
      setError(e.message || 'Delete failed');
    }
  };

  const domains = useMemo(() => {
    const values = new Set(
      groups
        .filter((g) => !filters.kind || dutyKind(g) === filters.kind)
        .map((g) => (g.duty && g.duty.includes(':') ? g.duty.split(':')[0] : 'other')),
    );
    return [...values].sort().map((value) => ({ value, label: value }));
  }, [groups, filters.kind]);

  const filterDefs = useMemo(() => [
    {
      key: 'kind',
      label: 'Kind',
      emptyLabel: 'All kinds',
      options: [
        ...(BRAND_DUTY_IDS.size ? [{ value: 'brand', label: PLATFORM_NAME }] : []),
        { value: 'platform', label: 'Platform' },
        { value: 'other', label: 'Core and other' },
      ],
    },
    { key: 'domain', label: 'Domain', emptyLabel: 'All domains', options: domains },
    {
      key: 'role_type',
      label: 'Type',
      emptyLabel: 'All types',
      options: [
        { value: 'platform', label: 'Platform' },
        { value: 'app', label: 'App' },
      ],
    },
  ], [domains]);

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    const rows = groups.filter((g) => {
      const duty = rowDuty(g);
      const domain = duty.includes(':') ? duty.split(':')[0] : 'other';
      if (filters.kind === 'brand' && !BRAND_DUTY_IDS.has(duty)) return false;
      if (filters.kind && filters.kind !== 'brand' && dutyKind(g) !== filters.kind) return false;
      if (filters.domain && domain !== filters.domain) return false;
      if (filters.role_type && g.role_type !== filters.role_type) return false;
      if (!q) return true;
      return [duty, g.name, g.manifest_key, g.description].filter(Boolean).join(' ').toLowerCase().includes(q);
    });
    if (filters.kind === 'brand') {
      rows.sort((a, b) => {
        const ia = BRAND_DUTIES.findIndex((d) => d.id === rowDuty(a));
        const ib = BRAND_DUTIES.findIndex((d) => d.id === rowDuty(b));
        return ia - ib;
      });
    }
    return rows;
  }, [groups, searchValue, filters]);

  const columns = useMemo(() => [
    {
      field: 'duty',
      headerName: 'Duty',
      flex: 1.1,
      minWidth: 180,
      valueGetter: (value, row) => row.duty || row.name,
      renderCell: (p) => <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{p.value}</Typography>,
    },
    { field: 'name', headerName: 'Stored group', flex: 1, minWidth: 160 },
    {
      field: 'app',
      headerName: 'App',
      width: 120,
      valueGetter: (value, row) => APP_BY_DUTY[rowDuty(row)] || '',
    },
    {
      field: 'role_type',
      headerName: 'Type',
      width: 110,
      valueGetter: (value, row) => (row.role_type === 'platform' ? 'Platform' : 'App'),
    },
    {
      field: 'users_count',
      headerName: 'Assignments',
      width: 120,
      valueGetter: (value, row) => row.users_count || 0,
    },
    {
      field: 'actions',
      headerName: '',
      width: 120,
      sortable: false,
      filterable: false,
      renderCell: (p) => (
        <Box>
          <Tooltip title="View duty">
            <IconButton
              size="small"
              aria-label="View duty"
              onClick={(e) => { e.stopPropagation(); navigate(`/admin/groups/${p.row.id}`); }}
            >
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit stored group">
            <IconButton size="small" aria-label="Edit stored group" onClick={(e) => { e.stopPropagation(); openEdit(p.row); }}>
              <EditRounded fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete stored group">
            <IconButton
              size="small"
              aria-label="Delete stored group"
              sx={{ color: 'error.main' }}
              onClick={(e) => { e.stopPropagation(); setDeleteTarget(p.row); }}
            >
              <DeleteRounded fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ], [navigate]);

  return (
    <>
      {error && <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError('')}>{error}</Alert>}
      <FilteredDataGrid
        title="Duties"
        description={`${PLATFORM_NAME} grants four duties: people:lead for People, platform:employee for My, platform:manager for Team, and platform:admin for the instance. A duty has no org unit. The eye opens it.`}
        actions={
          <Button variant="contained" size="small" startIcon={<AddRounded />} onClick={openCreate}>
            New stored group
          </Button>
        }
        rows={filteredRows}
        columns={columns}
        loading={loading}
        countLabel={`${filteredRows.length} of ${groups.length} duties`}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder="Search duty, stored group…"
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => { setSearchValue(''); setFilters(EMPTY_FILTERS); }}
        emptyMessage="No duties match."
        highlightRow={(row) => row.id === highlightRow}
        onRowClick={(params) => setHighlightRow(params.row.id)}
      />

      <SystemDialog
        open={dialogOpen}
        title={editingId ? 'Edit stored group' : 'New stored group'}
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        cancelLabel="Cancel"
        actions={(
          <Button variant="contained" size="small" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        )}
        width={480}
        height={320}
        minWidth={400}
        minHeight={260}
      >
        <Box px={2} py={1} sx={{ display: 'grid', gap: 2 }}>
          <TextField
            label="Stored group name"
            fullWidth
            required
            size="small"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            helperText="This is the alias stored in the database. Domain duties such as people:lead are defined in the catalog."
          />
          <TextField
            label="Description"
            fullWidth
            size="small"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Box>
      </SystemDialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete stored group"
        message={deleteTarget ? `Delete ${deleteTarget.name}? Assignments that use it are removed with it.` : ''}
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  );
}
