// src/pages/DataEntryPage.jsx
import React, { useEffect, useState } from "react";
import {
  Box, Typography, Button, IconButton, Dialog, DialogTitle, DialogContent, DialogActions,
  Table, TableHead, TableRow, TableCell, TableBody, Tooltip, CircularProgress
} from "@mui/material";
import { Add, Edit, Delete } from "@mui/icons-material";
import { useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { fetchModules } from "../api/modules";
import { fetchDataSchemaTables, fetchDataSchemaFields } from "../api/dataschema";
import { apiFetch } from "../api/api";



function DataRowForm({ open, onClose, onSubmit, fields, initial }) {
  const [values, setValues] = useState(initial?.values || {});

  useEffect(() => {
    setValues(initial?.values || {});
  }, [initial]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{initial ? "Edit Row" : "New Row"}</DialogTitle>
      <DialogContent>
        <Box gap={2} display="flex" flexDirection="column" mt={1}>
          {fields.map((f) => (
            <div key={f.name} style={{ marginBottom: 10 }}>
              <label>
                <b>{f.label}:</b>
                <input
                  type="text"
                  value={values[f.name] ?? ""}
                  onChange={e => setValues(v => ({ ...v, [f.name]: e.target.value }))}
                  style={{ marginLeft: 8, padding: 6, width: "75%" }}
                  disabled={f.type === "reference"}
                />
              </label>
            </div>
          ))}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit">Cancel</Button>
        <Button
          onClick={() => onSubmit({ values })}
          variant="contained"
        >
          {initial ? "Save" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function DataEntryPage() {
  const { moduleName, tableId } = useParams();
  const { user, currentContext } = useAuth();
  const [loading, setLoading] = useState(true);
  const [table, setTable] = useState(null);
  const [fields, setFields] = useState([]);
  const [rows, setRows] = useState([]);
  const [openForm, setOpenForm] = useState(false);
  const [editing, setEditing] = useState(null);

  // Load table and fields
  useEffect(() => {
    if (!user || !currentContext) return;
    setLoading(true);
    fetchModules(user.token, currentContext.context_id).then(modules => {
      const mod = modules.find(m => m.name.toLowerCase() === moduleName.toLowerCase());
      if (!mod) { setLoading(false); return; }
      fetchDataSchemaTables(user.token, currentContext.context_id, mod.id).then(tables => {
        const t = (tables || []).find(t => String(t.id) === String(tableId));
        setTable(t || null);
        if (t) {
          fetchDataSchemaFields(user.token, t.id, currentContext.context_id).then(flds => {
            setFields(flds || []);
            setLoading(false);
          });
        } else {
          setLoading(false);
        }
      });
    });
  }, [user, currentContext, moduleName, tableId]);

  // Load rows
  const loadRows = () => {
    if (!user || !currentContext || !tableId) return;
    apiFetch(`/api/dataschema/rows/?data_table=${tableId}`, { token: user.token, context_id: currentContext.context_id })
      .then(rs => setRows(rs || []));
  };
  useEffect(() => { if (tableId) loadRows(); }, [tableId, user, currentContext]);

  const handleCreate = async (data) => {
    await apiFetch(`/api/dataschema/rows/`, {
      method: "POST",
      token: user.token,
      context_id: currentContext.context_id,
      body: { ...data, data_table: tableId },
    });
    setOpenForm(false);
    setEditing(null);
    loadRows();
  };

  const handleEdit = async (data) => {
    await apiFetch(`/api/dataschema/rows/${editing.id}/`, {
      method: "PUT",
      token: user.token,
      context_id: currentContext.context_id,
      body: { ...editing, ...data, data_table: tableId },
    });
    setOpenForm(false);
    setEditing(null);
    loadRows();
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Archive this row?")) return;
    await apiFetch(`/api/dataschema/rows/${id}/`, {
      method: "DELETE",
      token: user.token,
      context_id: currentContext.context_id,
    });
    loadRows();
  };

  if (loading) return <CircularProgress sx={{ m:4 }} />;
  if (!table || !fields.length) return <Box p={4}>Table or fields not found.</Box>;

  return (
    <Box p={3}>
      <Typography variant="h5" gutterBottom>
        {table.title} – Data Entries
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        {table.description}
      </Typography>
      <Box mb={2} display="flex" justifyContent="flex-end">
        <Button startIcon={<Add />} variant="contained" onClick={() => { setEditing(null); setOpenForm(true); }}>
          New Row
        </Button>
      </Box>
      <Table size="small">
        <TableHead>
          <TableRow>
            {fields.map(f => (
              <TableCell key={f.name}>{f.label}</TableCell>
            ))}
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {(rows || []).map((row) => (
            <TableRow key={row.id}>
              {fields.map(f => (
                <TableCell key={f.name}>
                  {typeof row.values?.[f.name] === "boolean"
                    ? (row.values[f.name] ? "Yes" : "No")
                    : row.values?.[f.name] ?? ""}
                </TableCell>
              ))}
              <TableCell>
                <Tooltip title="Edit">
                  <IconButton size="small" onClick={() => { setEditing(row); setOpenForm(true); }}>
                    <Edit fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Delete/Archive">
                  <IconButton size="small" onClick={() => handleDelete(row.id)}>
                    <Delete fontSize="small" />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <DataRowForm
        open={openForm}
        onClose={() => { setOpenForm(false); setEditing(null); }}
        onSubmit={editing ? handleEdit : handleCreate}
        fields={fields}
        initial={editing}
      />
    </Box>
  );
}
