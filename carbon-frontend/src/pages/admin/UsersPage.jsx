// src/pages/admin/UsersPage.jsx
// Admin page: create + manage user accounts. Role-gated by AdminRoute.
// Admin shell: FilteredDataGrid (search + Active/Staff filters) + SystemDialog + ConfirmDialog
// (RULE_16, RULE_8). API via apiFetch wrappers (RULE_10); admin copy is plain English.
import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Box, Typography, Button, IconButton, TextField,
  Chip, Alert, Switch, FormControlLabel, Stack, Tooltip,
} from "@mui/material";
import AddRounded from "@mui/icons-material/AddRounded";
import EditRounded from "@mui/icons-material/EditRounded";
import DeleteRounded from "@mui/icons-material/DeleteRounded";
import useDocumentTitle from '../../hooks/useDocumentTitle';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import { useAuth } from "../../auth/AuthContext";
import { fetchUsers, createUser, updateUser, deleteUser } from "../../api/users";

const EMPTY_FORM = { username: "", email: "", password: "", is_active: true };

export default function UsersPage() {
  useDocumentTitle("Users");
  const { user } = useAuth();
  const token = user?.token;

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [searchValue, setSearchValue] = useState("");
  const [filters, setFilters] = useState({ is_active: "", is_staff: "" });
  /** Read-only linked Employee identity shown when editing (not editable here). */
  const [linkedEmployee, setLinkedEmployee] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    fetchUsers(token)
      .then((data) => setUsers(data))
      .catch((e) => setError(e.message || "Failed to load users"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setLinkedEmployee(null);
    setDialogOpen(true);
  };

  const openEdit = (u) => {
    setEditingId(u.id);
    setForm({ username: u.username, email: u.email || "", password: "", is_active: u.is_active });
    setLinkedEmployee(
      u.employee_full_name || u.employee_no || u.employee_org_unit
        ? {
            full_name: u.employee_full_name || null,
            employee_no: u.employee_no || null,
            org_unit: u.employee_org_unit || null,
            position: u.employee_position || null,
          }
        : null
    );
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.username.trim()) { setError("Username is required."); return; }
    if (!editingId && !form.password) { setError("Password is required for a new user."); return; }
    setSaving(true);
    setError("");
    try {
      if (editingId) {
        const payload = { email: form.email.trim(), is_active: form.is_active };
        if (form.password) payload.password = form.password;
        await updateUser(token, editingId, payload);
      } else {
        await createUser(token, {
          username: form.username.trim(),
          email: form.email.trim(),
          password: form.password,
          is_active: form.is_active,
        });
      }
      setDialogOpen(false);
      load();
    } catch (e) {
      setError(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setError("");
    try {
      await deleteUser(token, deleteTarget.id);
      setDeleteTarget(null);
      load();
    } catch (e) {
      setError(e.message || "Delete failed");
    }
  };

  const filterDefs = useMemo(
    () => [
      {
        key: 'is_active',
        label: 'Active',
        emptyLabel: 'All',
        options: [
          { value: 'true', label: 'Active' },
          { value: 'false', label: 'Inactive' },
        ],
      },
      {
        key: 'is_staff',
        label: 'Staff',
        emptyLabel: 'All',
        options: [
          { value: 'true', label: 'Yes' },
          { value: 'false', label: 'No' },
        ],
      },
    ],
    []
  );

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return users.filter((u) => {
      if (q) {
        const hay = [
          u.username,
          u.email,
          u.employee_full_name,
          u.employee_no,
          u.employee_org_unit,
          u.employee_position,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (filters.is_active === 'true' && !u.is_active) return false;
      if (filters.is_active === 'false' && u.is_active) return false;
      if (filters.is_staff === 'true' && !u.is_staff) return false;
      if (filters.is_staff === 'false' && u.is_staff) return false;
      return true;
    });
  }, [users, searchValue, filters]);

  const columns = useMemo(
    () => [
      {
        field: 'username',
        headerName: 'Username',
        flex: 1,
        minWidth: 140,
        renderCell: (p) => <Typography sx={{ fontWeight: 600 }}>{p.value}</Typography>,
      },
      {
        field: 'employee_full_name',
        headerName: 'Employee',
        flex: 1,
        minWidth: 160,
        valueGetter: (value, row) => row.employee_full_name || '—',
      },
      {
        field: 'employee_no',
        headerName: 'Emp. No',
        width: 110,
        valueGetter: (value, row) => row.employee_no || '—',
      },
      {
        field: 'employee_org_unit',
        headerName: 'Home org',
        flex: 1.2,
        minWidth: 180,
        valueGetter: (value, row) => row.employee_org_unit || '—',
      },
      {
        field: 'employee_position',
        headerName: 'Position',
        flex: 1,
        minWidth: 180,
        valueGetter: (value, row) => row.employee_position || '—',
      },
      {
        field: 'email',
        headerName: 'Email',
        flex: 1,
        minWidth: 180,
        valueGetter: (value, row) => row.email || '—',
      },
      {
        field: 'is_active',
        headerName: 'Active',
        width: 110,
        renderCell: (p) => (
          <Chip
            size="small"
            label={p.value ? 'Active' : 'Inactive'}
            color={p.value ? 'success' : 'default'}
          />
        ),
      },
      {
        field: 'is_staff',
        headerName: 'Staff',
        width: 90,
        valueGetter: (value, row) => (row.is_staff ? 'Yes' : 'No'),
      },
      {
        field: 'actions',
        headerName: '',
        width: 100,
        sortable: false,
        filterable: false,
        renderCell: (p) => (
          <Box>
            <Tooltip title="Edit user">
              <IconButton size="small" onClick={() => openEdit(p.row)} aria-label="Edit user">
                <EditRounded fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete user">
              <IconButton
                size="small"
                sx={{ color: 'error.main' }}
                onClick={() => setDeleteTarget(p.row)}
                aria-label="Delete user"
              >
                <DeleteRounded fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ),
      },
    ],
    []
  );

  return (
    <>
      {error && <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError("")}>{error}</Alert>}

      <FilteredDataGrid
        title="Users"
        description="Accounts, linked employee, home org, and position. Position profiles and Assignments grant duties."
        actions={
          <Button variant="contained" size="small" startIcon={<AddRounded />} onClick={openCreate}>
            New User
          </Button>
        }
        rows={filteredRows}
        columns={columns}
        loading={loading}
        countLabel={`${filteredRows.length} of ${users.length} users`}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder="Search username, employee, emp. no, org…"
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => {
          setSearchValue('');
          setFilters({ is_active: '', is_staff: '' });
        }}
        emptyMessage="No users yet."
        emptySubtext="Create your first user account."
      />

      {/* Create / edit dialog */}
      <SystemDialog
        open={dialogOpen}
        title={editingId ? "Edit User" : "New User"}
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        cancelLabel="Cancel"
        actions={
          <Button variant="contained" size="small" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        }
        width={480}
        height={460}
        minWidth={400}
        minHeight={360}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
      >
        <Box px={2} py={1}>
          <Stack spacing={2}>
            <TextField
              label="Username" fullWidth required size="small"
              value={form.username} disabled={!!editingId}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
            {linkedEmployee && (
              <Alert severity="info" variant="outlined">
                Linked employee: {linkedEmployee.full_name || '—'}
                {linkedEmployee.employee_no ? ` (${linkedEmployee.employee_no})` : ''}
                {linkedEmployee.org_unit ? ` · ${linkedEmployee.org_unit}` : ''}
                {linkedEmployee.position ? ` · ${linkedEmployee.position}` : ''}
                . Edit people records in Employees — not here.
              </Alert>
            )}
            <TextField
              label="Email" type="email" fullWidth size="small"
              value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <TextField
              label={editingId ? "New password (leave blank to keep)" : "Password"}
              type="password" fullWidth size="small"
              required={!editingId}
              value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
            <FormControlLabel
              control={<Switch checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />}
              label="Active"
            />
          </Stack>
        </Box>
      </SystemDialog>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete User?"
        message={deleteTarget ? `Delete user "${deleteTarget.username}"? This cannot be undone.` : ''}
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  );
}
