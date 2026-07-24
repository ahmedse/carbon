// src/pages/admin/tabs/GroupRoleAssignmentsTab.jsx
import React, { useEffect, useState, useMemo } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  MenuItem,
  TextField,
  Alert,
  Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import SystemDialog from '../../../components/SystemDialog';
import StandardDataGrid from '../../../components/StandardDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import {
  fetchGroupMembers,
  fetchGroupScopedAssignments,
} from '../../../api/groups';
import {
  fetchUsers,
  fetchGroups,
  createScopedRole,
  deleteScopedRole,
  updateScopedRole,
} from '../../../api/accessControl';
import { fetchOrgUnits } from '../../../api/orgUnits';

const EMPTY_FORM = { user: '', group: '', org_unit: '', module: null, is_active: true };

export default function GroupRoleAssignmentsTab({ entityData: group }) {
  const { user } = useAuth();
  const token = user?.token;

  const [loading, setLoading] = useState(true);
  const [members, setMembers] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [error, setError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);

  const loadData = async () => {
    if (!group?.id) return;
    setLoading(true);
    setError(null);
    try {
      const [membersData, scopedData, usersData, groupsData, orgUnitsData] = await Promise.all([
        fetchGroupMembers(token, group.id),
        fetchGroupScopedAssignments(token, group.id),
        fetchUsers(token),
        fetchGroups(token),
        fetchOrgUnits(token),
      ]);
      setMembers(Array.isArray(membersData) ? membersData : []);
      setAssignments(Array.isArray(scopedData) ? scopedData : []);
      setUsers(Array.isArray(usersData) ? usersData : []);
      setGroups(Array.isArray(groupsData) ? groupsData : []);
      setOrgUnits(Array.isArray(orgUnitsData) ? orgUnitsData : []);
    } catch (err) {
      setError(err.message || 'Failed to load role assignments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [group?.id, token]);

  const openCreate = () => {
    setError(null);
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (row) => {
    setError(null);
    setEditing(row);
    setForm({
      user: row.user_id || '',
      group: row.group_id || group.id,
      org_unit: row.org_unit_id || '',
      module: row.module_id || null,
      is_active: row.is_active,
      scoped_role_id: row.id,
    });
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
  };

  const handleSave = async () => {
    if (!form.user || !form.group) {
      setError('User and role are required.');
      return;
    }
    setSaving(true);
    setError(null);

    const payload = {
      user: form.user,
      group: form.group,
      org_unit: form.org_unit === '' ? null : form.org_unit,
      module: form.module,
      is_active: Boolean(form.is_active),
    };

    try {
      if (editing) {
        await updateScopedRole(token, editing.scoped_role_id, payload);
      } else {
        await createScopedRole(token, payload);
      }
      await loadData();
      closeDialog();
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (row) => {
    if (!window.confirm(`Remove role assignment for ${row.user}?`)) return;
    setError(null);
    try {
      await deleteScopedRole(token, row.id);
      await loadData();
    } catch (err) {
      setError(err.message || 'Delete failed');
    }
  };

  const rows = useMemo(() => {
    return [
      ...members.map((m) => ({
        id: `global-${m.id}`,
        rowId: m.scoped_role_id,
        user: m.username,
        email: m.email,
        org_unit: 'Global',
        module: 'Global',
        status: 'Active',
        assigned_at: new Date(m.assigned_at).toLocaleString(),
        isGlobal: true,
      })),
      ...assignments.map((a) => ({
        id: `scoped-${a.id}`,
        rowId: a.id,
        user: a.user,
        email: '',
        org_unit: a.org_unit || '—',
        module: a.module || '—',
        status: a.is_active ? 'Active' : 'Inactive',
        assigned_at: new Date(a.created_at).toLocaleString(),
        isGlobal: false,
      })),
    ];
  }, [members, assignments]);

  const columns = [
    { field: 'user', headerName: 'User', minWidth: 160, flex: 1 },
    { field: 'email', headerName: 'Email', minWidth: 180, flex: 1 },
    { field: 'org_unit', headerName: 'Org Unit', minWidth: 180, flex: 1 },
    { field: 'module', headerName: 'Module', minWidth: 180, flex: 1 },
    { field: 'status', headerName: 'Status', minWidth: 120, flex: 0.7 },
    { field: 'assigned_at', headerName: 'Assigned At', minWidth: 180, flex: 1 },
    {
      field: 'actions',
      headerName: 'Actions',
      minWidth: 160,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size='small' variant='outlined' onClick={() => openEdit(params.row)}>
            Edit
          </Button>
          <Button size='small' variant='outlined' color='error' onClick={() => handleDelete(params.row)}>
            Delete
          </Button>
        </Box>
      ),
    },
  ];

  return (
    <Box sx={{ p: 3 }}>
      {error && <Alert severity='error' sx={{ mb: 2 }}>{error}</Alert>}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant='h6'>Role assignments</Typography>
          <Typography variant='body2' color='text.secondary'>Manage both global and scoped role assignments for this group.</Typography>
        </Box>
        <Button variant='contained' startIcon={<AddRounded />} onClick={openCreate}>Add assignment</Button>
      </Box>

      {loading ? (
        <Box sx={{ textAlign: 'center', py: 6 }}><CircularProgress /></Box>
      ) : (
        <StandardDataGrid
          rows={rows}
          columns={columns}
          loading={loading}
          toolbar
          pageSize={25}
          rowsPerPageOptions={[25, 50, 100]}
        />
      )}

      <SystemDialog
        open={dialogOpen}
        title={editing ? 'Edit role assignment' : 'Create role assignment'}
        onClose={closeDialog}
        onCancel={closeDialog}
        actions={(
          <Button variant='contained' onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        )}
        width={760}
        height={520}
        fullWidth={false}
      >
        <Box sx={{ display: 'grid', gap: 2 }}>
          <TextField
            label='User'
            select
            fullWidth
            value={form.user}
            onChange={(e) => setForm({ ...form, user: e.target.value })}
            size='small'
          >
            <MenuItem value=''>Select user</MenuItem>
            {users.map((u) => <MenuItem key={u.id} value={u.id}>{u.username}</MenuItem>)}
          </TextField>
          <TextField
            label='Role'
            select
            fullWidth
            value={form.group}
            onChange={(e) => setForm({ ...form, group: e.target.value })}
            size='small'
          >
            <MenuItem value=''>Select role</MenuItem>
            {groups.map((g) => <MenuItem key={g.id} value={g.id}>{g.name}</MenuItem>)}
          </TextField>
          <TextField
            label='Org Unit'
            select
            fullWidth
            value={form.org_unit}
            onChange={(e) => setForm({ ...form, org_unit: e.target.value })}
            size='small'
            helperText='Leave blank for global role assignment.'
          >
            <MenuItem value=''>Global</MenuItem>
            {orgUnits.map((o) => <MenuItem key={o.id} value={o.id}>{o.full_path || o.name}</MenuItem>)}
          </TextField>
          <TextField
            label='Status'
            select
            fullWidth
            value={form.is_active ? 'active' : 'inactive'}
            onChange={(e) => setForm({ ...form, is_active: e.target.value === 'active' })}
            size='small'
          >
            <MenuItem value='active'>Active</MenuItem>
            <MenuItem value='inactive'>Inactive</MenuItem>
          </TextField>
        </Box>
      </SystemDialog>
    </Box>
  );
}
