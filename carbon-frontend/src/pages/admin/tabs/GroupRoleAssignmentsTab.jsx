// Assignments of one duty. Each row is one user and one anchor org unit.
import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Alert, Box, Button, IconButton, Tooltip, Typography } from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import DeleteRounded from '@mui/icons-material/DeleteRounded';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import SystemDialog from '../../../components/SystemDialog';
import ConfirmDialog from '../../../components/ConfirmDialog';
import FilteredDataGrid from '../../../components/FilteredDataGrid';
import { SearchSelect } from '../../../components/Form';
import { useAuth } from '../../../auth/AuthContext';
import { fetchGroupScopedAssignments } from '../../../api/groups';
import { fetchUsers, createScopedRole, deleteScopedRole } from '../../../api/accessControl';
import { fetchOrgUnits } from '../../../api/orgUnits';

const EMPTY_FORM = { user: '', org_unit: '' };

function dateLabel(value) {
  return value || 'Open';
}

export default function GroupRoleAssignmentsTab({ entityData: group }) {
  const { user } = useAuth();
  const token = user?.token;

  const [loading, setLoading] = useState(true);
  const [assignments, setAssignments] = useState([]);
  const [users, setUsers] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [error, setError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [viewRow, setViewRow] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({ provenance: '', scope: '' });
  const [highlightRow, setHighlightRow] = useState(null);

  const loadData = useCallback(async () => {
    if (!group?.id) return;
    setLoading(true);
    setError(null);
    try {
      const [scopedData, usersData, orgUnitsData] = await Promise.all([
        fetchGroupScopedAssignments(token, group.id),
        fetchUsers(token),
        fetchOrgUnits(token),
      ]);
      setAssignments(Array.isArray(scopedData) ? scopedData : []);
      setUsers(Array.isArray(usersData) ? usersData : []);
      setOrgUnits(Array.isArray(orgUnitsData) ? orgUnitsData : []);
    } catch (err) {
      setError(err.message || 'Failed to load assignments');
    } finally {
      setLoading(false);
    }
  }, [token, group?.id]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async () => {
    if (!form.user) { setError('User is required.'); return; }
    setSaving(true);
    setError(null);
    try {
      await createScopedRole(token, {
        user: form.user,
        group: group.id,
        org_unit: form.org_unit === '' ? null : form.org_unit,
        is_active: true,
      });
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      await loadData();
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setError(null);
    try {
      await deleteScopedRole(token, deleteTarget.id);
      setDeleteTarget(null);
      await loadData();
    } catch (err) {
      setError(err.message || 'Delete failed');
    }
  };

  const filterDefs = useMemo(() => [
    {
      key: 'provenance',
      label: 'Provenance',
      emptyLabel: 'All',
      options: [
        { value: 'birthright', label: 'Birthright' },
        { value: 'exception', label: 'Exception' },
      ],
    },
    {
      key: 'scope',
      label: 'Anchor',
      emptyLabel: 'All anchors',
      options: [
        { value: 'global', label: 'Global' },
        { value: 'org', label: 'One org unit' },
      ],
    },
  ], []);

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return assignments.filter((a) => {
      if (filters.provenance && a.provenance !== filters.provenance) return false;
      if (filters.scope === 'global' && a.org_unit) return false;
      if (filters.scope === 'org' && !a.org_unit) return false;
      if (!q) return true;
      return [a.employee_name, a.user, a.org_unit, a.duty].filter(Boolean).join(' ').toLowerCase().includes(q);
    });
  }, [assignments, searchValue, filters]);

  const columns = useMemo(() => [
    {
      field: 'employee_name',
      headerName: 'Employee',
      flex: 1.3,
      minWidth: 200,
      valueGetter: (value, row) => row.employee_name || row.user,
      renderCell: (p) => (
        <Box sx={{ lineHeight: 1.2 }}>
          <Typography variant="body2">{p.row.employee_name || p.row.user}</Typography>
          {p.row.employee_name ? (
            <Typography variant="caption" color="text.secondary">{p.row.user}</Typography>
          ) : null}
        </Box>
      ),
    },
    {
      field: 'org_unit',
      headerName: 'Anchor org unit',
      flex: 1.2,
      minWidth: 180,
      valueGetter: (value, row) => row.org_unit || 'Global',
    },
    {
      field: 'provenance',
      headerName: 'Provenance',
      width: 120,
      valueGetter: (value, row) => (row.provenance === 'birthright' ? 'Birthright' : 'Exception'),
    },
    { field: 'valid_from', headerName: 'From', width: 110, valueGetter: (value, row) => dateLabel(row.valid_from) },
    { field: 'valid_to', headerName: 'Until', width: 110, valueGetter: (value, row) => dateLabel(row.valid_to) },
    {
      field: 'actions',
      headerName: '',
      width: 90,
      sortable: false,
      filterable: false,
      renderCell: (p) => (
        <Box>
          <Tooltip title="View assignment">
            <IconButton size="small" aria-label="View assignment" onClick={(e) => { e.stopPropagation(); setViewRow(p.row); }}>
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={p.row.provenance === 'birthright' ? 'Birthright follows position and org' : 'Remove exception'}>
            <span>
              <IconButton
                size="small"
                aria-label="Remove exception"
                disabled={p.row.provenance === 'birthright'}
                sx={{ color: 'error.main' }}
                onClick={(e) => { e.stopPropagation(); setDeleteTarget(p.row); }}
              >
                <DeleteRounded fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      ),
    },
  ], []);

  const orgOptions = orgUnits.map((o) => ({ id: o.id, name: o.full_path || o.name }));

  return (
    <Box sx={{ p: 2 }}>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Each row grants {group?.duty || group?.name || 'this duty'} to one user on one anchor org unit. Global means no anchor.
      </Typography>
      <FilteredDataGrid
        embedded
        title="Assignments"
        description={`Each row grants ${group?.duty || group?.name || 'this duty'} to one user on one anchor org unit.`}
        actions={
          <Button variant="contained" size="small" startIcon={<AddRounded />} onClick={() => { setForm(EMPTY_FORM); setDialogOpen(true); }}>
            Grant exception
          </Button>
        }
        rows={filteredRows}
        columns={columns}
        loading={loading}
        countLabel={`${filteredRows.length} of ${assignments.length}`}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder="Search user or org unit…"
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => { setSearchValue(''); setFilters({ provenance: '', scope: '' }); }}
        emptyMessage="No assignments for this duty."
        highlightRow={(row) => row.id === highlightRow}
        onRowClick={(params) => setHighlightRow(params.row.id)}
        height={420}
      />

      <SystemDialog
        open={dialogOpen}
        title="Grant exception"
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        cancelLabel="Cancel"
        actions={(
          <Button variant="contained" size="small" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Grant'}
          </Button>
        )}
        width={480}
        height={360}
        minWidth={400}
        minHeight={300}
      >
        <Box px={2} py={1} sx={{ display: 'grid', gap: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Duty {group?.duty || group?.name}. One anchor on this row.
          </Typography>
          <SearchSelect
            label="User"
            required
            options={users}
            valueKey="id"
            labelKey="username"
            value={form.user}
            onChange={(v) => setForm({ ...form, user: v?.id ?? '' })}
          />
          <SearchSelect
            label="Anchor org unit"
            options={orgOptions}
            valueKey="id"
            labelKey="name"
            value={form.org_unit}
            onChange={(v) => setForm({ ...form, org_unit: v?.id ?? '' })}
            helperText="Empty means global. Another org unit is another row."
          />
        </Box>
      </SystemDialog>

      <SystemDialog
        open={Boolean(viewRow)}
        title="Assignment"
        onClose={() => setViewRow(null)}
        onCancel={() => setViewRow(null)}
        cancelLabel="Close"
        width={440}
        height={340}
        minWidth={380}
        minHeight={260}
      >
        {viewRow && (
          <Box px={2} py={1} sx={{ display: 'grid', gap: 1 }}>
            <Typography variant="body2"><b>Employee.</b> {viewRow.employee_name || viewRow.user}</Typography>
            <Typography variant="body2"><b>User.</b> {viewRow.user}</Typography>
            <Typography variant="body2"><b>Duty.</b> {viewRow.duty || group?.duty || group?.name}</Typography>
            <Typography variant="body2"><b>Anchor org unit.</b> {viewRow.org_unit || 'Global'}</Typography>
            <Typography variant="body2"><b>Provenance.</b> {viewRow.provenance === 'birthright' ? 'Birthright' : 'Exception'}</Typography>
            <Typography variant="body2"><b>From.</b> {dateLabel(viewRow.valid_from)} <b>Until.</b> {dateLabel(viewRow.valid_to)}</Typography>
          </Box>
        )}
      </SystemDialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Remove exception"
        message={deleteTarget ? `Remove ${deleteTarget.employee_name || deleteTarget.user} on ${deleteTarget.org_unit || 'global'}?` : ''}
        confirmLabel="Remove"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </Box>
  );
}
