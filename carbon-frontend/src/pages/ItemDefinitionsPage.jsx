// File: src/pages/ItemDefinitionsPage.jsx

import React, { useEffect, useState } from "react";
import {
  Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, MenuItem, IconButton, Tooltip, Chip, Switch, FormControlLabel
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { Add, Edit, Delete, Archive, Info } from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";
import { useNotification } from "../components/NotificationProvider";
import {
  fetchItems, createItem, updateItem, deleteItem, fetchItemUsage
} from "../api/items";

const DATA_TYPE_CHOICES = [
  { value: "number", label: "Number" },
  { value: "string", label: "String" },
  { value: "date", label: "Date" },
  { value: "file", label: "File" },
  { value: "select", label: "Select" },
];

const TIME_UNIT_CHOICES = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "quarter", label: "Quarter" },
  { value: "year", label: "Year" },
];

export default function ItemDefinitionsPage() {
  const { user, currentContext } = useAuth();
  const { notify } = useNotification();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  // Debug: print user and context
  useEffect(() => {
    // console.log("[DEBUG] USER:", user);
    // console.log("[DEBUG] CONTEXT:", currentContext);
  }, [user, currentContext]);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  // Item form state
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [usage, setUsage] = useState(null);
  const [usageLoading, setUsageLoading] = useState(false);

  // Fetch all items for current context
  const loadItems = async () => {
    setLoading(true);
    console.log("[DEBUG] loadItems called, user:", user, "context:", currentContext);
    try {
      const data = await fetchItems(user.token, currentContext.context_id);
      setRows(data || []);
    } catch (e) {
      notify({ message: "Failed to load items.", type: "error" });
      console.error("[DEBUG] loadItems error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user && currentContext) loadItems();
    // eslint-disable-next-line
  }, [user, currentContext]);

  // Open modal for add/edit
  const openModal = (row = null) => {
    setEditing(row);
    setForm(row ? { ...row } : { required: true, editable: true });
    setErrors({});
    setModalOpen(true);
    setUsage(null);
    if (row) {
      setUsageLoading(true);
      fetchItemUsage(user.token, row.id, currentContext.context_id)
        .then(setUsage)
        .catch(() => setUsage(null))
        .finally(() => setUsageLoading(false));
    }
  };

  // Validate form
  const validate = () => {
    const errs = {};
    if (!form.name || form.name.length < 2) errs.name = "Name required.";
    if (!form.data_type) errs.data_type = "Data type required.";
    if (!form.time_unit) errs.time_unit = "Time unit required.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // Handle form field change
  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }));

  // Save (add or edit)
  const handleSave = async () => {
    if (!validate()) return;
    try {
      if (editing) {
        await updateItem(user.token, editing.id, currentContext.context_id, form);
        notify({ message: "Item updated.", type: "success" });
      } else {
        await createItem(user.token, currentContext.context_id, form);
        notify({ message: "Item created.", type: "success" });
      }
      setModalOpen(false);
      loadItems();
    } catch (e) {
      notify({ message: e.message || "Save failed.", type: "error" });
    }
  };

  // Delete or archive
  const handleDelete = async (row) => {
    // Check usage first
    let usageInfo = usage;
    if (!usage) {
      setUsageLoading(true);
      usageInfo = await fetchItemUsage(user.token, row.id, currentContext.context_id).catch(() => null);
      setUsageLoading(false);
    }
    if (usageInfo && usageInfo.entries_count > 0) {
      notify({ message: "Cannot delete: this item is used in entries. Archive instead.", type: "warning" });
      return;
    }
    if (!window.confirm("Are you sure you want to delete this item? This cannot be undone.")) return;
    try {
      await deleteItem(user.token, row.id, currentContext.context_id);
      notify({ message: "Item deleted.", type: "success" });
      loadItems();
    } catch (e) {
      notify({ message: e.message || "Delete failed.", type: "error" });
    }
  };

  // Columns for DataGrid
  const columns = [
    { field: "name", headerName: "Name", flex: 1, minWidth: 120 },
    { field: "data_type", headerName: "Data Type", width: 100 },
    { field: "units", headerName: "Units", width: 80 },
    { field: "time_unit", headerName: "Time Unit", width: 90 },
    { field: "category", headerName: "Category", width: 100 },
    { field: "required", headerName: "Required", width: 80, type: "boolean" },
    { field: "editable", headerName: "Editable", width: 80, type: "boolean" },
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
      )
    }
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" fontWeight={800} mb={2}>Item Definitions</Typography>
      <Box mb={2}>
        <Button variant="contained" startIcon={<Add />} onClick={() => openModal(null)}>
          Add Item
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
        <DialogTitle>{editing ? "Edit Item" : "Add Item"}</DialogTitle>
        <DialogContent>
          <Box component="form" sx={{ display: "flex", flexWrap: "wrap", gap: 2, mt: 1 }}>
            <TextField
              label="Name"
              value={form.name || ""}
              onChange={e => setField("name", e.target.value)}
              error={!!errors.name}
              helperText={errors.name}
              required
              fullWidth
            />
            <TextField
              label="Description"
              value={form.description || ""}
              onChange={e => setField("description", e.target.value)}
              multiline
              rows={2}
              fullWidth
            />
            <TextField
              select
              label="Data Type"
              value={form.data_type || ""}
              onChange={e => setField("data_type", e.target.value)}
              error={!!errors.data_type}
              helperText={errors.data_type}
              required
              sx={{ minWidth: 120 }}
            >
              {DATA_TYPE_CHOICES.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
            <TextField
              label="Units"
              value={form.units || ""}
              onChange={e => setField("units", e.target.value)}
              sx={{ minWidth: 80 }}
            />
            <TextField
              select
              label="Time Unit"
              value={form.time_unit || ""}
              onChange={e => setField("time_unit", e.target.value)}
              error={!!errors.time_unit}
              helperText={errors.time_unit}
              required
              sx={{ minWidth: 120 }}
            >
              {TIME_UNIT_CHOICES.map(opt => (
                <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
              ))}
            </TextField>
            <TextField
              label="Category"
              value={form.category || ""}
              onChange={e => setField("category", e.target.value)}
              sx={{ minWidth: 100 }}
            />
            <TextField
              label="Tags (comma separated)"
              value={form.tags ? form.tags.join(", ") : ""}
              onChange={e => setField("tags", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
              sx={{ minWidth: 140 }}
            />
            {form.data_type === "select" && (
              <TextField
                label="Options (comma separated)"
                value={form.options ? form.options.join(", ") : ""}
                onChange={e => setField("options", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
                sx={{ minWidth: 160 }}
              />
            )}
            <FormControlLabel
              control={
                <Switch
                  checked={form.required || false}
                  onChange={e => setField("required", e.target.checked)}
                />
              }
              label="Required"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.editable || false}
                  onChange={e => setField("editable", e.target.checked)}
                />
              }
              label="Editable"
            />
            {/* validation_rules, evidence_rules as JSON */}
            <TextField
              label="Validation Rules (JSON)"
              value={JSON.stringify(form.validation_rules || {}, null, 2)}
              onChange={e => {
                try {
                  setField("validation_rules", JSON.parse(e.target.value));
                  setErrors(e => ({ ...e, validation_rules: undefined }));
                } catch {
                  setErrors(e => ({ ...e, validation_rules: "Invalid JSON" }));
                }
              }}
              error={!!errors.validation_rules}
              helperText={errors.validation_rules}
              multiline
              minRows={2}
              sx={{ minWidth: 160 }}
            />
            <TextField
              label="Evidence Rules (JSON)"
              value={JSON.stringify(form.evidence_rules || {}, null, 2)}
              onChange={e => {
                try {
                  setField("evidence_rules", JSON.parse(e.target.value));
                  setErrors(e => ({ ...e, evidence_rules: undefined }));
                } catch {
                  setErrors(e => ({ ...e, evidence_rules: "Invalid JSON" }));
                }
              }}
              error={!!errors.evidence_rules}
              helperText={errors.evidence_rules}
              multiline
              minRows={2}
              sx={{ minWidth: 160 }}
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
                    <Chip label={`Templates: ${usage.templates_count}`} size="small" sx={{ ml: 1, mr: 1 }} />
                    <Chip label={`Entries: ${usage.entries_count}`} size="small" sx={{ mr: 1 }} />
                    {usage.entries_count > 0 && (
                      <Tooltip title="Cannot delete this item because it is used in entries. You can only archive or edit.">
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