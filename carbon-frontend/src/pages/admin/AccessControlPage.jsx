// src/pages/admin/AccessControlPage.jsx
// Admin page: assign users a role scoped to an org unit. Role-gated by AdminRoute.
import React, { useEffect, useState, useCallback } from "react";
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  MenuItem, Chip, CircularProgress, Alert,
} from "@mui/material";
import AddRounded from "@mui/icons-material/AddRounded";
import DeleteRounded from "@mui/icons-material/DeleteRounded";
import { useAuth } from "../../auth/AuthContext";
import { fetchOrgUnits } from "../../api/orgUnits";
import {
  fetchUsers, fetchGroups, fetchScopedRoles, createScopedRole, deleteScopedRole,
} from "../../api/accessControl";

const EMPTY_FORM = { user: "", group: "", org_unit: "" };

export default function AccessControlPage() {
  const { user } = useAuth();
  const token = user?.token;

  const [assignments, setAssignments] = useState([]);
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    Promise.all([
      fetchScopedRoles(token),
      fetchUsers(token),
      fetchGroups(token),
      fetchOrgUnits(token),
    ])
      .then(([a, u, g, o]) => {
        setAssignments(a);
        setUsers(u);
        setGroups(g);
        setOrgUnits(o);
      })
      .catch((e) => setError(e.message || "Failed to load access data"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => { setForm(EMPTY_FORM); setDialogOpen(true); };

  const handleSave = async () => {
    if (!form.user || !form.group) { setError("User and Role are required."); return; }
    setSaving(true);
    setError("");
    const payload = {
      user: form.user,
      group: form.group,
      org_unit: form.org_unit === "" ? null : form.org_unit,
      module: null,
      is_active: true,
    };
    try {
      await createScopedRole(token, payload);
      setDialogOpen(false);
      load();
    } catch (e) {
      setError(e.message || "Failed to create assignment");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (a) => {
    if (!window.confirm(`Remove ${a.user}'s "${a.group}" role${a.org_unit ? " on " + a.org_unit : " (global)"}?`)) return;
    setError("");
    try {
      await deleteScopedRole(token, a.id);
      load();
    } catch (e) {
      setError(e.message || "Delete failed");
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>Access Control</Typography>
          <Typography variant="body2" color="text.secondary">
            Assign users a role scoped to an org unit. A role on an org unit also applies to its sub-units.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddRounded />} onClick={openCreate}>
          Assign Role
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}

      {loading ? (
        <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>User</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Org Unit</TableCell>
              <TableCell>Scope</TableCell>
              <TableCell>Active</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {assignments.length === 0 && (
              <TableRow><TableCell colSpan={6}>No role assignments yet.</TableCell></TableRow>
            )}
            {assignments.map((a) => (
              <TableRow key={a.id}>
                <TableCell><b>{a.user}</b></TableCell>
                <TableCell><Chip size="small" label={a.group} /></TableCell>
                <TableCell>{a.org_unit || "—"}</TableCell>
                <TableCell>{a.org_unit ? "Org unit" : "Global"}</TableCell>
                <TableCell>{a.is_active ? "Yes" : "No"}</TableCell>
                <TableCell align="right">
                  <IconButton size="small" color="error" onClick={() => handleDelete(a)}>
                    <DeleteRounded fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Assign Role</DialogTitle>
        <DialogContent>
          <TextField
            label="User" select fullWidth required margin="normal"
            value={form.user} onChange={(e) => setForm({ ...form, user: e.target.value })}
          >
            {users.map((u) => <MenuItem key={u.id} value={u.id}>{u.username}</MenuItem>)}
          </TextField>
          <TextField
            label="Role" select fullWidth required margin="normal"
            value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })}
          >
            {groups.map((g) => <MenuItem key={g.id} value={g.id}>{g.name}</MenuItem>)}
          </TextField>
          <TextField
            label="Org Unit" select fullWidth margin="normal"
            value={form.org_unit} onChange={(e) => setForm({ ...form, org_unit: e.target.value })}
            helperText="Leave as Global to grant across the whole organisation."
          >
            <MenuItem value="">— Global (whole organisation) —</MenuItem>
            {orgUnits.map((o) => (
              <MenuItem key={o.id} value={o.id}>{o.full_path || o.name}</MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Assign"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
