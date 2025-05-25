// frontend/src/pages/AdminDashboard/ModuleTemplateEntries.jsx

import React, { useEffect, useState } from "react";
import {
  Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Table, TableBody, TableCell, TableHead, TableRow, IconButton, MenuItem, Select
} from "@mui/material";
import { Add, Edit, Delete } from "@mui/icons-material";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../api";

/**
 * ModuleTemplateEntries
 * - Ensures user has admin role for context.
 * - Fetches template, fields, and entries for the current context and template.
 * - Provides CRUD for entries.
 */
export default function ModuleTemplateEntries() {
  const { module, templateId } = useParams();
  const navigate = useNavigate();
  const { user, currentContext } = useAuth();
  const token = user?.token;

  // Only allow if user is admin in this context
  const isAdmin = (user?.roles || []).some(
    r =>
      (r.role === "admin" || r.role === "admin_role") &&
      (!currentContext?.project || r.project === currentContext.project)
  );
  const context_type = currentContext?.context_type;
  const context_name = currentContext?.[context_type];
  const context = { context_type, context_name };

  // State
  const [template, setTemplate] = useState(null);
  const [fields, setFields] = useState([]);
  const [entries, setEntries] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(true);

  // Fetch template, its fields, and entries
  useEffect(() => {
    if (!token || !templateId || !context_type || !context_name) return;

    setLoading(true);
    apiFetch(`/api/datacollection/templates/${templateId}/`, { token, context })
      .then(res => res.json())
      .then(tpl => {
        setTemplate(tpl);
        setFields(tpl.fields || []);
        // Fetch entries for this template in this context
        return apiFetch(`/api/datacollection/entries/?template=${templateId}`, { token, context });
      })
      .then(res => res.json())
      .then(setEntries)
      .finally(() => setLoading(false));
  }, [token, templateId, context_type, context_name]);

  // Permission check
  if (!isAdmin) {
    return (
      <Box>
        <Typography color="error">You do not have permission to manage entries for this template.</Typography>
      </Box>
    );
  }

  // Handlers
  const handleOpen = (entry = null) => {
    setEditing(entry);
    setForm(
      entry
        ? { ...entry.data, period_start: entry.period_start, period_end: entry.period_end }
        : fields.reduce(
            (acc, f) => ({ ...acc, [f.id]: f.data_type === "select" ? "" : "" }),
            { period_start: "", period_end: "" }
          )
    );
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setEditing(null);
  };

  const handleChange = e => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  // Submit (Add/Edit)
  const handleSubmit = async () => {
    const method = editing ? "PUT" : "POST";
    const endpoint = editing
      ? `/api/datacollection/entries/${editing.id}/`
      : "/api/datacollection/entries/";
    const body = {
      template: Number(templateId),
      template_version: template?.version,
      context, // context will be extracted in backend
      data: fields.reduce((obj, f) => ({ ...obj, [f.id]: form[f.id] }), {}),
      period_start: form.period_start,
      period_end: form.period_end,
    };
    await apiFetch(endpoint, { method, body, token, context });
    setOpen(false);
    // Refresh entries
    apiFetch(`/api/datacollection/entries/?template=${templateId}`, { token, context })
      .then(res => res.json())
      .then(setEntries);
  };

  // Delete
  const handleDelete = async (entry) => {
    if (!window.confirm("Delete this entry?")) return;
    await apiFetch(`/api/datacollection/entries/${entry.id}/`, {
      method: "DELETE",
      token,
      context,
    });
    // Refresh
    apiFetch(`/api/datacollection/entries/?template=${templateId}`, { token, context })
      .then(res => res.json())
      .then(setEntries);
  };

  // Render
  if (loading) return <Typography>Loading...</Typography>;
  if (!template) return <Typography color="error">Template not found.</Typography>;

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">
          {template.name} Entries
          {currentContext && currentContext.project && <> (Project: {currentContext.project})</>}
          {currentContext && currentContext.module && <> (Module: {currentContext.module})</>}
        </Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => handleOpen()}>
          Add Entry
        </Button>
      </Box>
      <Table>
        <TableHead>
          <TableRow>
            {fields.map(f => (
              <TableCell key={f.id}>{f.name}</TableCell>
            ))}
            <TableCell>Period Start</TableCell>
            <TableCell>Period End</TableCell>
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {entries.map(entry => (
            <TableRow key={entry.id}>
              {fields.map(f => (
                <TableCell key={f.id}>{entry.data?.[f.id]}</TableCell>
              ))}
              <TableCell>{entry.period_start}</TableCell>
              <TableCell>{entry.period_end}</TableCell>
              <TableCell>
                <IconButton onClick={() => handleOpen(entry)}><Edit /></IconButton>
                <IconButton onClick={() => handleDelete(entry)}><Delete /></IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Dialog for Add/Edit */}
      <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? "Edit Entry" : "Add Entry"}</DialogTitle>
        <DialogContent>
          {fields.map(f => (
            <Box key={f.id} mb={2}>
              {f.data_type === "select" ? (
                <Select
                  fullWidth
                  name={String(f.id)}
                  value={form[f.id] || ""}
                  onChange={handleChange}
                  label={f.name}
                >
                  {(f.options || []).map(opt => (
                    <MenuItem key={opt} value={opt}>{opt}</MenuItem>
                  ))}
                </Select>
              ) : (
                <TextField
                  margin="dense"
                  fullWidth
                  label={f.name}
                  name={String(f.id)}
                  type={f.data_type === "number" ? "number" : f.data_type}
                  value={form[f.id] || ""}
                  onChange={handleChange}
                />
              )}
            </Box>
          ))}
          <TextField
            margin="dense"
            fullWidth
            label="Period Start"
            name="period_start"
            type="date"
            value={form.period_start || ""}
            onChange={handleChange}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            margin="dense"
            fullWidth
            label="Period End"
            name="period_end"
            type="date"
            value={form.period_end || ""}
            onChange={handleChange}
            InputLabelProps={{ shrink: true }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}