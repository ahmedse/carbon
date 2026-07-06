// src/pages/admin/UsersPage.jsx
// Admin page: create + manage user accounts. Role-gated by AdminRoute.
import React, { useEffect, useState, useCallback } from "react";
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  Chip, CircularProgress, Alert, Switch, FormControlLabel,
} from "@mui/material";
import AddRounded from "@mui/icons-material/AddRounded";
import EditRounded from "@mui/icons-material/EditRounded";
import DeleteRounded from "@mui/icons-material/DeleteRounded";
import { useAuth } from "../../auth/AuthContext";
import { fetchUsers, createUser, updateUser, deleteUser } from "../../api/users";

const EMPTY_FORM = { username: "", email: "", password: "", is_active: true };

export default function UsersPage() {
  const { user } = useAuth();
  const token = user?.token;

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

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
    setDialogOpen(true);
  };

  const openEdit = (u) => {
    setEditingId(u.id);
    setForm({ username: u.username, email: u.email || "", password: "", is_active: u.is_active });
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

  const handleDelete = async (u) => {
    if (!window.confirm(`Delete user "${u.username}"? This cannot be undone.`)) return;
    setError("");
    try {
      await deleteUser(token, u.id);
      load();
    } catch (e) {
      setError(e.message || "Delete failed");
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>Users</Typography>
          <Typography variant="body2" color="text.secondary">
            Create and manage user accounts. Assign roles on the Access Control page.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddRounded />} onClick={openCreate}>
          New User
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}

      {loading ? (
        <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Username</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Active</TableCell>
              <TableCell>Staff</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.length === 0 && (
              <TableRow><TableCell colSpan={5}>No users yet.</TableCell></TableRow>
            )}
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell><b>{u.username}</b></TableCell>
                <TableCell>{u.email || "—"}</TableCell>
                <TableCell>
                  <Chip size="small" label={u.is_active ? "Active" : "Inactive"} color={u.is_active ? "success" : "default"} />
                </TableCell>
                <TableCell>{u.is_staff ? "Yes" : "No"}</TableCell>
                <TableCell align="right">
                  <IconButton size="small" onClick={() => openEdit(u)}><EditRounded fontSize="small" /></IconButton>
                  <IconButton size="small" color="error" onClick={() => handleDelete(u)}><DeleteRounded fontSize="small" /></IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingId ? "Edit User" : "New User"}</DialogTitle>
        <DialogContent>
          <TextField
            label="Username" fullWidth required margin="normal"
            value={form.username} disabled={!!editingId}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />
          <TextField
            label="Email" type="email" fullWidth margin="normal"
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <TextField
            label={editingId ? "New password (leave blank to keep)" : "Password"}
            type="password" fullWidth margin="normal"
            required={!editingId}
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <FormControlLabel
            control={<Switch checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />}
            label="Active"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
