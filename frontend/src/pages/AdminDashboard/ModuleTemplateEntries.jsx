// File: frontend/src/pages/AdminDashboard/ModuleTemplateEntries.jsx

import React, { useEffect, useState } from "react";
import {
  Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Table, TableBody, TableCell, TableHead, TableRow, IconButton, MenuItem, Select
} from "@mui/material";
import { Add, Edit, Delete } from "@mui/icons-material";
import { useParams } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../api";

export default function ModuleTemplateEntries() {
  const { submenu, module, templateId } = useParams();
  const { user, currentContext } = useAuth();
  const token = user?.token;

  // Admin check (you can adjust this as needed for your RBAC)
  const isAdmin = (user?.roles || []).some(
    r =>
      (r.role === "admin" || r.role === "admin_role") &&
      (!currentContext?.project || r.project === currentContext.project)
  );
  const context_id = currentContext?.context_id;
  const context = { context_id }; // Pass this to apiFetch

  console.log("[AuthContext] Setting currentContext:", currentContext);

  // State for items/templates
  const [rows, setRows] = useState([]);
  const [fields, setFields] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(true);

  // Titles and API endpoints per submenu
  const isItems = submenu === "data-items";
  const isTemplates = submenu === "templates";
  const title = isItems ? "Data Items" : isTemplates ? "Templates" : "Entries";
  const endpoint = isItems
    ? "/api/datacollection/item-definitions/"
    : isTemplates
    ? "/api/datacollection/templates/"
    : null;

  // Table columns
  const itemColumns = [
    { key: "name", label: "Name" },
    { key: "data_type", label: "Data Type" },
    { key: "category", label: "Category" },
    { key: "required", label: "Required" },
    { key: "editable", label: "Editable" },
    { key: "units", label: "Units" },
    { key: "module", label: "Module" },
  ];
  const templateColumns = [
    { key: "name", label: "Name" },
    { key: "description", label: "Description" },
    { key: "version", label: "Version" },
    { key: "status", label: "Status" },
    { key: "module", label: "Module" },
  ];

  // Fetch data for items or templates
  useEffect(() => {
    if (!token || !context_id || !endpoint) return;
    setLoading(true);
    apiFetch(endpoint, { token, context })
      .then(res => res.json())
      .then(data => {
        setRows(Array.isArray(data) ? data : []);
        if (isTemplates && Array.isArray(data) && data.length) {
          setFields([]);
        }
      })
      .finally(() => setLoading(false));
  }, [token, context_id, endpoint, submenu]);

  // Open dialog for Add/Edit
  const handleOpen = (row = null) => {
    setEditing(row);
    setForm(row ? { ...row } : {});
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setEditing(null);
  };

  // Change handler
  const handleChange = e => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  // Submit (Add/Edit)
  const handleSubmit = async () => {
    const method = editing ? "PUT" : "POST";
    const url = editing ? `${endpoint}${editing.id}/` : endpoint;
    await apiFetch(url, { method, body: form, token, context });
    setOpen(false);
    // Refresh
    apiFetch(endpoint, { token, context })
      .then(res => res.json())
      .then(setRows);
  };

  // Delete
  const handleDelete = async (row) => {
    if (!window.confirm("Delete this entry?")) return;
    await apiFetch(`${endpoint}${row.id}/`, { method: "DELETE", token, context });
    apiFetch(endpoint, { token, context })
      .then(res => res.json())
      .then(setRows);
  };

  // Render
  if (!isAdmin) {
    return <Typography color="error">You do not have permission to manage {title.toLowerCase()}.</Typography>;
  }
  if (loading) return <Typography>Loading...</Typography>;

  // Decide columns
  const columns = isItems ? itemColumns : isTemplates ? templateColumns : [];

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">{title}</Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => handleOpen()}>
          Add {isItems ? "Item" : "Template"}
        </Button>
      </Box>
      <Table>
        <TableHead>
          <TableRow>
            {columns.map(col => (
              <TableCell key={col.key}>{col.label}</TableCell>
            ))}
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map(row => (
            <TableRow key={row.id}>
              {columns.map(col => (
                <TableCell key={col.key}>{String(row[col.key] ?? "")}</TableCell>
              ))}
              <TableCell>
                <IconButton onClick={() => handleOpen(row)}><Edit /></IconButton>
                <IconButton onClick={() => handleDelete(row)}><Delete /></IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Dialog for Add/Edit */}
      <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? `Edit ${isItems ? "Item" : "Template"}` : `Add ${isItems ? "Item" : "Template"}`}</DialogTitle>
        <DialogContent>
          {columns.map(col => (
            <TextField
              key={col.key}
              margin="dense"
              fullWidth
              label={col.label}
              name={col.key}
              value={form[col.key] || ""}
              onChange={handleChange}
              type={col.key === "required" || col.key === "editable" ? "checkbox" : "text"}
            />
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}