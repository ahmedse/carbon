import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, TextField, Chip, CircularProgress, Alert,
} from '@mui/material';
import SystemDialog from '../../components/SystemDialog';
import { useNavigate } from 'react-router-dom';
import AddRounded from '@mui/icons-material/AddRounded';
import EditRounded from '@mui/icons-material/EditRounded';
import DeleteRounded from '@mui/icons-material/DeleteRounded';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import { useAuth } from '../../auth/AuthContext';
import { apiFetch } from '../../api/api';

const EMPTY_FORM = { name: '', description: '' };

export default function GroupsPage() {
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

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('accounts/groups/', { method: 'GET', token }); // groups list
      if (!res.ok) throw new Error('Failed to load groups');
      const data = await res.json();
      setGroups(Array.isArray(data) ? data : data.results || []);
    } catch (e) {
      setError(e.message || 'Failed to load groups');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setEditingId(null); setForm(EMPTY_FORM); setDialogOpen(true); };
  const openEdit = (group) => { setEditingId(group.id); setForm({ name: group.name, description: group.description || '' }); setDialogOpen(true); };

  const handleSave = async () => {
    if (!form.name.trim()) { setError('Group name is required.'); return; }
    setSaving(true);
    setError('');
    try {
      const body = { name: form.name.trim(), description: form.description };
      const res = await apiFetch(editingId ? `accounts/groups/${editingId}/` : 'accounts/groups/', {
        method: editingId ? 'PUT' : 'POST',
        token,
        body,
      }); // save group
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || body.detail || 'Failed to save group');
      }
      setDialogOpen(false);
      load();
    } catch (e) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (group) => {
    if (!window.confirm(`Delete group "${group.name}"?`)) return;
    setError('');
    try {
      const res = await apiFetch(`accounts/groups/${group.id}/`, {
        method: 'DELETE',
        token,
      }); // delete group
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || body.detail || 'Delete failed');
      }
      load();
    } catch (e) {
      setError(e.message || 'Delete failed');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box>
          <Typography variant='h5' fontWeight={700}>Groups & Roles</Typography>
          <Typography variant='body2' color='text.secondary'>Manage platform role groups and their membership shape.</Typography>
        </Box>
        <Button variant='contained' startIcon={<AddRounded />} onClick={openCreate}>New Group</Button>
      </Box>

      {error && <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {loading ? (
        <Box sx={{ textAlign: 'center', py: 6 }}><CircularProgress /></Box>
      ) : (
        <Table size='small'>
          <TableHead>
            <TableRow>
              <TableCell>Group</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Scoped</TableCell>
              <TableCell>Users</TableCell>
              <TableCell>Permissions</TableCell>
              <TableCell align='right'>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {groups.length === 0 && <TableRow><TableCell colSpan={6}>No groups yet.</TableCell></TableRow>}
            {groups.map((group) => (
              <TableRow key={group.id} hover>
                <TableCell sx={{ cursor: 'pointer' }} onClick={() => navigate(`/admin/groups/${group.id}`)}>
                  <Box>
                    <Typography variant='body2' fontWeight={600}>{group.name}</Typography>
                    <Typography variant='caption' color='text.secondary'>
                      {group.manifest_key || (group.role_type === 'platform' ? 'Platform role' : 'App role')}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>{group.role_type === 'platform' ? 'Platform' : 'App'}</TableCell>
                <TableCell>{group.is_scoped ? 'Yes' : 'No'}</TableCell>
                <TableCell><Chip size='small' label={group.users_count || 0} /></TableCell>
                <TableCell><Chip size='small' color='primary' label={group.permissions_count || 0} /></TableCell>
                <TableCell align='right'>
                  <IconButton size='small' onClick={() => navigate(`/admin/groups/${group.id}`)}><VisibilityRounded fontSize='small' /></IconButton>
                  <IconButton size='small' onClick={() => openEdit(group)}><EditRounded fontSize='small' /></IconButton>
                  <IconButton size='small' color='error' onClick={() => handleDelete(group)}><DeleteRounded fontSize='small' /></IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <SystemDialog
        open={dialogOpen}
        title={editingId ? 'Edit Group' : 'New Group'}
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        cancelLabel='Cancel'
        actions={(
          <Button variant='contained' onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        )}
        width={560}
        height={360}
        minWidth={420}
        minHeight={320}
        maxWidth='calc(100vw - 32px)'
        maxHeight='calc(100vh - 32px)'
      >
        <Box px={2} py={1}>
          <TextField
            label='Group name'
            fullWidth
            margin='normal'
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <TextField
            label='Description'
            fullWidth
            margin='normal'
            multiline
            rows={4}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Box>
      </SystemDialog>
    </Box>
  );
}
