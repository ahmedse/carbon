// src/pages/admin/OrgUnitsPage.jsx
// Admin page: view + manage the OrgUnit tree. Role-gated by AdminRoute in App.jsx.
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  MenuItem, Chip, CircularProgress, Alert,
} from "@mui/material";
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddRounded from "@mui/icons-material/AddRounded";
import EditRounded from "@mui/icons-material/EditRounded";
import DeleteRounded from "@mui/icons-material/DeleteRounded";
import VisibilityRounded from "@mui/icons-material/VisibilityRounded";
import { useAuth } from "../../auth/AuthContext";
import {
  fetchOrgUnits, createOrgUnit, updateOrgUnit, deleteOrgUnit,
} from "../../api/orgUnits";

const ORG_TYPES = [
  "university", "campus", "college", "department", "division", "team", "facility", "other",
];

const EMPTY_FORM = { name: "", org_type: "department", parent: "", code: "", description: "" };

export default function OrgUnitsPage() {
  useDocumentTitle("Org Units");
  const navigate = useNavigate();
  const { user } = useAuth();
  const token = user?.token;

  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    fetchOrgUnits(token)
      .then((data) => setUnits(data))
      .catch((e) => setError(e.message || "Failed to load org units"))
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
    setForm({
      name: u.name || "",
      org_type: u.org_type || "department",
      parent: u.parent || "",
      code: u.code || "",
      description: u.description || "",
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { setError("Name is required."); return; }
    setSaving(true);
    setError("");
    const payload = {
      name: form.name.trim(),
      org_type: form.org_type,
      parent: form.parent === "" ? null : form.parent,
      code: form.code.trim(),
      description: form.description.trim(),
    };
    try {
      if (editingId) await updateOrgUnit(token, editingId, payload);
      else await createOrgUnit(token, payload);
      setDialogOpen(false);
      load();
    } catch (e) {
      setError(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (u) => {
    if (!window.confirm(`Delete org unit "${u.name}"? This cannot be undone.`)) return;
    setError("");
    try {
      await deleteOrgUnit(token, u.id);
      load();
    } catch (e) {
      setError(e.message || "Delete failed");
    }
  };

  const nameById = Object.fromEntries(units.map((u) => [u.id, u.name]));

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>Organisation Units</Typography>
          <Typography variant="body2" color="text.secondary">
            Manage the org structure (campuses, colleges, departments). Data ownership and access are scoped to these units.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddRounded />} onClick={openCreate}>
          New Org Unit
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}

      {loading ? (
        <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Parent</TableCell>
              <TableCell>Code</TableCell>
              <TableCell>Path</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {units.length === 0 && (
              <TableRow><TableCell colSpan={6}>No org units yet.</TableCell></TableRow>
            )}
            {units.map((u) => (
              <TableRow key={u.id}>
                <TableCell><b>{u.name}</b></TableCell>
                <TableCell><Chip size="small" label={u.org_type} /></TableCell>
                <TableCell>{u.parent ? (nameById[u.parent] || u.parent) : "—"}</TableCell>
                <TableCell>{u.code || "—"}</TableCell>
                <TableCell sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>{u.full_path || u.name}</TableCell>
                <TableCell align="right">
                  <IconButton size="small" onClick={() => navigate(`/admin/org-units/${u.id}`)} color="primary"><VisibilityRounded fontSize="small" /></IconButton>
                  <IconButton size="small" onClick={() => openEdit(u)}><EditRounded fontSize="small" /></IconButton>
                  <IconButton size="small" color="error" onClick={() => handleDelete(u)}><DeleteRounded fontSize="small" /></IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingId ? "Edit Org Unit" : "New Org Unit"}</DialogTitle>
        <DialogContent>
          <TextField
            label="Name" fullWidth required margin="normal"
            value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <TextField
            label="Type" select fullWidth margin="normal"
            value={form.org_type} onChange={(e) => setForm({ ...form, org_type: e.target.value })}
          >
            {ORG_TYPES.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
          </TextField>
          <TextField
            label="Parent" select fullWidth margin="normal"
            value={form.parent} onChange={(e) => setForm({ ...form, parent: e.target.value })}
          >
            <MenuItem value="">— None (top level) —</MenuItem>
            {units.filter((u) => u.id !== editingId).map((u) => (
              <MenuItem key={u.id} value={u.id}>{u.full_path || u.name}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Code" fullWidth margin="normal"
            value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })}
          />
          <TextField
            label="Description" fullWidth multiline minRows={2} margin="normal"
            value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
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
