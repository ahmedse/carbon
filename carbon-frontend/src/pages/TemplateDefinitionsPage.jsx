// File: src/pages/TemplateDefinitionsPage.jsx

import React, { useEffect, useState } from "react";
import {
  Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, MenuItem, IconButton, Tooltip, Chip, Switch, FormControlLabel, Autocomplete
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { Add, Edit, Delete, Archive, Info } from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "../components/NotificationProvider";
import {
  fetchTemplates, createTemplate, updateTemplate, deleteTemplate, fetchTemplateUsage
} from "../api/templates";
import { fetchItems } from "../api/items";
import { fetchModules } from "../api/modules"; // You may need to implement this

const STATUS_CHOICES = [
  { value: "active", label: "Active" },
  { value: "archived", label: "Archived" },
];

export default function TemplateDefinitionsPage() {
  const { user, currentContext } = useAuth();
  const { notify } = useNotification();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [usage, setUsage] = useState(null);
  const [usageLoading, setUsageLoading] = useState(false);

  // Modules and items for the current project
  const [modules, setModules] = useState([]);
  const [items, setItems] = useState([]);
  const [availableItems, setAvailableItems] = useState([]);

  // Load all templates for this project
  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await fetchTemplates(user.token, currentContext.context_id);
      setRows(data || []);
    } catch (e) {
      notify({ message: "Failed to load templates.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  // Load modules for this project
  const loadModules = async () => {
    try {
      const modules = await fetchModules(user.token, currentContext.context_id);
      setModules(modules || []);
    } catch {
      setModules([]);
    }
  };

  // Load all items for this project (to later filter by module)
  const loadItems = async () => {
    try {
      const data = await fetchItems(user.token, currentContext.context_id);
      setItems(data || []);
    } catch {
      setItems([]);
    }
  };

  useEffect(() => {
    if (user && currentContext) {
      loadTemplates();
      loadModules();
      loadItems();
    }
    // eslint-disable-next-line
  }, [user, currentContext]);

  // Open modal for add/edit
  const openModal = (row = null) => {
    setEditing(row);
    setForm(
      row
        ? {
            ...row,
            fields: row.fields || [],
            module: row.module || "",
            status: row.status || "active",
          }
        : {
            name: "",
            description: "",
            version: 1,
            status: "active",
            module: "",
            fields: [],
          }
    );
    setErrors({});
    setModalOpen(true);
    setUsage(null);
    if (row) {
      setUsageLoading(true);
      fetchTemplateUsage(user.token, row.id, currentContext.context_id)
        .then(setUsage)
        .catch(() => setUsage(null))
        .finally(() => setUsageLoading(false));
    }
  };

  // When module changes, update available items
  useEffect(() => {
    if (!form.module) {
      setAvailableItems([]);
    } else {
      setAvailableItems(items.filter(item => item.module === form.module));
    }
  }, [form.module, items]);

  // Validate form
  const validate = () => {
    const errs = {};
    if (!form.name || form.name.length < 2) errs.name = "Name required.";
    if (!form.module) errs.module = "Module required.";
    if (!form.fields || form.fields.length === 0) errs.fields = "At least one field required.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // Save (add or edit)
  const handleSave = async () => {
    if (!validate()) return;
    try {
      if (editing) {
        await updateTemplate(user.token, editing.id, currentContext.context_id, {
          ...form,
          fields: form.fields.map(f => f.id || f), // Ensure ids
        });
        notify({ message: "Template updated.", type: "success" });
      } else {
        await createTemplate(user.token, currentContext.context_id, {
          ...form,
          fields: form.fields.map(f => f.id || f),
        });
        notify({ message: "Template created.", type: "success" });
      }
      setModalOpen(false);
      loadTemplates();
    } catch (e) {
      notify({ message: e.message || "Save failed.", type: "error" });
    }
  };

  // Delete or archive
  const handleDelete = async (row) => {
    let usageInfo = usage;
    if (!usage) {
      setUsageLoading(true);
      usageInfo = await fetchTemplateUsage(user.token, row.id, currentContext.context_id).catch(() => null);
      setUsageLoading(false);
    }
    if (usageInfo && usageInfo.entries_count > 0) {
      notify({ message: "Cannot delete: this template is used in entries. Archive instead.", type: "warning" });
      return;
    }
    if (!window.confirm("Are you sure you want to delete this template? This cannot be undone.")) return;
    try {
      await deleteTemplate(user.token, row.id, currentContext.context_id);
      notify({ message: "Template deleted.", type: "success" });
      loadTemplates();
    } catch (e) {
      notify({ message: e.message || "Delete failed.", type: "error" });
    }
  };

  // Columns for DataGrid
  const columns = [
    { field: "name", headerName: "Name", flex: 1, minWidth: 120 },
    { field: "module", headerName: "Module", width: 120 },
    { field: "version", headerName: "Version", width: 80 },
    { field: "status", headerName: "Status", width: 90 },
    {
      field: "fields",
      headerName: "Fields",
      width: 160,
      renderCell: (params) =>
        params.value?.map((f) =>
          typeof f === "object" ? f.name : f
        ).join(", "),
    },
    {
      field: "actions",
      headerName: "Actions",
      width: 130,
      sortable: false,
      renderCell: (params) => (
        <>
          <Tooltip title="Edit">
            <span>
              <IconButton size="small" onClick={() => openModal(params.row)}>
                <Edit fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Delete/Archive">
            <span>
              <IconButton size="small" color="error" onClick={() => handleDelete(params.row)}>
                <Delete fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </>
      ),
    },
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" fontWeight={800} mb={2}>
        Templates
      </Typography>
      <Box mb={2}>
        <Button variant="contained" startIcon={<Add />} onClick={() => openModal(null)}>
          Add Template
        </Button>
      </Box>
      <DataGrid
        autoHeight
        rows={rows}
        columns={columns}
        pageSize={10}
        rowsPerPageOptions={[10, 20, 50]}
        loading={loading}
        disableSelectionOnClick
        getRowId={row => row.id}
        sx={{ bgcolor: "background.paper", borderRadius: 2 }}
      />

      {/* Add/Edit Modal */}
      <Dialog open={modalOpen} onClose={() => setModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? "Edit Template" : "Add Template"}</DialogTitle>
        <DialogContent>
          <Box component="form" sx={{ display: "flex", flexWrap: "wrap", gap: 2, mt: 1 }}>
            <TextField
              label="Name"
              value={form.name || ""}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              error={!!errors.name}
              helperText={errors.name}
              required
              fullWidth
            />
            <TextField
              label="Description"
              value={form.description || ""}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              multiline
              rows={2}
              fullWidth
            />
            <TextField
              select
              label="Module"
              value={form.module || ""}
              onChange={e => setForm(f => ({ ...f, module: e.target.value, fields: [] }))}
              error={!!errors.module}
              helperText={errors.module}
              required
              sx={{ minWidth: 160 }}
              fullWidth
            >
              {modules.map(mod => (
                <MenuItem key={mod.name || mod.id} value={mod.name || mod.id}>
                  {mod.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Version"
              type="number"
              value={form.version || 1}
              onChange={e => setForm(f => ({ ...f, version: Number(e.target.value) }))}
              sx={{ minWidth: 90 }}
              fullWidth
            />
            <TextField
              select
              label="Status"
              value={form.status || "active"}
              onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
              sx={{ minWidth: 120 }}
              fullWidth
            >
              {STATUS_CHOICES.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
            <Autocomplete
              multiple
              options={availableItems}
              getOptionLabel={option => option.name}
              value={form.fields || []}
              onChange={(_, value) => setForm(f => ({ ...f, fields: value }))}
              filterSelectedOptions
              isOptionEqualToValue={(opt, val) => opt.id === val.id}
              renderInput={params => (
                <TextField
                  {...params}
                  label="Fields"
                  error={!!errors.fields}
                  helperText={errors.fields}
                  required
                  fullWidth
                />
              )}
              sx={{ minWidth: 200 }}
            />
          </Box>
          {/* Usage info if editing */}
          {editing && (
            <Box mt={3}>
              <Typography variant="subtitle2" color="text.secondary">
                Usage
                {usageLoading ? (
                  <span> ...</span>
                ) : usage ? (
                  <>
                    <Chip label={`Entries: ${usage.entries_count}`} size="small" sx={{ ml: 1, mr: 1 }} />
                    {usage.entries_count > 0 && (
                      <Tooltip title="Cannot delete this template because it is used in entries. You can only archive or edit.">
                        <Info color="warning" fontSize="small" />
                      </Tooltip>
                    )}
                  </>
                ) : null}
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setModalOpen(false)}>Cancel</Button>
          <Button onClick={handleSave} variant="contained">
            {editing ? "Update" : "Create"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}