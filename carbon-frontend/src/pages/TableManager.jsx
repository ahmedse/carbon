// src/pages/TableManager.jsx
import React, { useEffect, useState } from "react";
import {
  Box, Typography, Tabs, Tab, Paper, Divider, Button, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, MenuItem, Select, Tooltip, CircularProgress
} from "@mui/material";
import { Add, Edit, Delete } from "@mui/icons-material";
import { useAuth } from "../auth/AuthContext";
import { fetchModules } from "../api/modules";
import {
  fetchDataSchemaTables, createDataSchemaTable, updateDataSchemaTable, deleteDataSchemaTable,
  fetchDataSchemaFields, createDataSchemaField, updateDataSchemaField, deleteDataSchemaField
} from "../api/dataschema";
import { ExpandLess, ExpandMore } from "@mui/icons-material";
import { Collapse } from "@mui/material";
// --- Field Editor ---
function FieldForm({ open, onClose, onSubmit, initial }) {
  const [name, setName] = useState(initial?.name || "");
  const [label, setLabel] = useState(initial?.label || "");
  const [type, setType] = useState(initial?.type || "string");
  const [required, setRequired] = useState(initial?.required || false);

  useEffect(() => {
    setName(initial?.name || "");
    setLabel(initial?.label || "");
    setType(initial?.type || "string");
    setRequired(initial?.required || false);
  }, [initial]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{initial ? "Edit Field" : "New Field"}</DialogTitle>
      <DialogContent>
        <Box gap={2} display="flex" flexDirection="column" mt={1}>
          <input
            autoFocus
            type="text"
            placeholder="Field Name"
            value={name}
            onChange={e => setName(e.target.value)}
            style={{ padding: 8, fontSize: 16, borderRadius: 4, border: "1px solid #ccc" }}
          />
          <input
            type="text"
            placeholder="Label"
            value={label}
            onChange={e => setLabel(e.target.value)}
            style={{ padding: 8, fontSize: 16, borderRadius: 4, border: "1px solid #ccc" }}
          />
          <Select
            value={type}
            onChange={e => setType(e.target.value)}
            fullWidth
            sx={{ minHeight: 40 }}
          >
            <MenuItem value="string">String</MenuItem>
            <MenuItem value="text">Text (Multiline)</MenuItem>
            <MenuItem value="number">Number</MenuItem>
            <MenuItem value="date">Date</MenuItem>
            <MenuItem value="boolean">Boolean</MenuItem>
            <MenuItem value="select">Single Select</MenuItem>
            <MenuItem value="multiselect">Multi Select</MenuItem>
            <MenuItem value="file">File</MenuItem>
            <MenuItem value="reference">Reference</MenuItem>
          </Select>
          <label>
            <input
              type="checkbox"
              checked={required}
              onChange={e => setRequired(e.target.checked)}
              style={{ marginRight: 8 }}
            />
            Required
          </label>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={() => onSubmit({ name, label, type, required })}
          variant="contained"
          disabled={!name.trim() || !label.trim()}
        >
          {initial ? "Save" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// --- Table Editor ---
function TableForm({ open, onClose, onSubmit, initial, modules }) {
  const [title, setTitle] = useState(initial?.title || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [moduleId, setModuleId] = useState(initial?.module || modules?.[0]?.id || "");

  useEffect(() => {
    setTitle(initial?.title || "");
    setDescription(initial?.description || "");
    setModuleId(initial?.module || modules?.[0]?.id || "");
  }, [initial, modules]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{initial ? "Edit Table" : "New Table"}</DialogTitle>
      <DialogContent>
        <Box gap={2} display="flex" flexDirection="column" mt={1}>
          <Select
            value={moduleId}
            onChange={e => setModuleId(e.target.value)}
            fullWidth
            sx={{ minHeight: 40 }}
          >
            {modules.map(m => (
              <MenuItem key={m.id} value={m.id}>{m.name}</MenuItem>
            ))}
          </Select>
          <input
            autoFocus
            type="text"
            placeholder="Title"
            value={title}
            onChange={e => setTitle(e.target.value)}
            style={{ padding: 8, fontSize: 16, borderRadius: 4, border: "1px solid #ccc" }}
          />
          <textarea
            placeholder="Description"
            value={description}
            onChange={e => setDescription(e.target.value)}
            rows={3}
            style={{ padding: 8, fontSize: 15, borderRadius: 4, border: "1px solid #ccc" }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={() => onSubmit({ title, description, module: moduleId })}
          variant="contained"
          disabled={!title.trim()}
        >
          {initial ? "Save" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function TableManager() {
  const { user, currentContext } = useAuth();
  const [modules, setModules] = useState([]);
  const [tablesByModule, setTablesByModule] = useState({});
  const [fieldsByTable, setFieldsByTable] = useState({});
  const [loading, setLoading] = useState(true);

  // Dialog state
  const [openTableForm, setOpenTableForm] = useState(false);
  const [editingTable, setEditingTable] = useState(null);
  const [openFieldForm, setOpenFieldForm] = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [currentTableId, setCurrentTableId] = useState(null); // For field form
  const [openModuleId, setOpenModuleId] = useState(null);

  // Load modules and tables
  useEffect(() => {
    if (!user || !currentContext) return;
    setLoading(true);
    fetchModules(user.token, currentContext.context_id).then((mods) => {
      setModules(mods || []);
      Promise.all(
        (mods || []).map(mod =>
          fetchDataSchemaTables(user.token, currentContext.context_id, mod.id).then(tables => ({
            module: mod,
            tables: tables || []
          }))
        )
      ).then(data => {
        const byMod = {};
        data.forEach(({ module, tables }) => {
          byMod[module.id] = tables;
        });
        setTablesByModule(byMod);
        setLoading(false);

        // Preload fields for all tables
        (data || []).forEach(({ tables }) => {
          (tables || []).forEach(table => {
            fetchDataSchemaFields(user.token, table.id, currentContext.context_id)
              .then(fields => {
                setFieldsByTable(prev => ({ ...prev, [table.id]: fields || [] }));
              });
          });
        });
      });
    });
  }, [user, currentContext]);

  // Table CRUD
  const handleCreateTable = async (data) => {
    await createDataSchemaTable(user.token, data, currentContext.context_id);
    setOpenTableForm(false);
    setEditingTable(null);
    // reload data
    // window.location.reload();
  };

  const handleEditTable = async (data) => {
    await updateDataSchemaTable(user.token, editingTable.id, { ...editingTable, ...data }, currentContext.context_id);
    setOpenTableForm(false);
    setEditingTable(null);
    window.location.reload();
  };

  const handleDeleteTable = async (table) => {
    if (!window.confirm(`Archive table "${table.title}"?`)) return;
    await deleteDataSchemaTable(user.token, table.id, currentContext.context_id);
    window.location.reload();
  };

  // Field CRUD
  const handleCreateField = async (data) => {
    await createDataSchemaField(user.token, { ...data, data_table: currentTableId }, currentContext.context_id);
    setOpenFieldForm(false);
    setEditingField(null);
    fetchDataSchemaFields(user.token, currentTableId, currentContext.context_id)
      .then(fields => setFieldsByTable(prev => ({ ...prev, [currentTableId]: fields || [] })));
  };

  const handleEditField = async (data) => {
    await updateDataSchemaField(user.token, editingField.id, { ...editingField, ...data }, currentContext.context_id);
    setOpenFieldForm(false);
    setEditingField(null);
    fetchDataSchemaFields(user.token, currentTableId, currentContext.context_id)
      .then(fields => setFieldsByTable(prev => ({ ...prev, [currentTableId]: fields || [] })));
  };

  const handleDeleteField = async (field) => {
    if (!window.confirm(`Archive field "${field.label}"?`)) return;
    await deleteDataSchemaField(user.token, field.id, currentContext.context_id);
    fetchDataSchemaFields(user.token, currentTableId, currentContext.context_id)
      .then(fields => setFieldsByTable(prev => ({ ...prev, [currentTableId]: fields || [] })));
  };

  if (loading) return <CircularProgress sx={{ m: 4 }} />;

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        Data Schema Manager <span style={{ fontWeight: 400, fontSize: 18, color: "#888" }}>(Define Data Tables)</span>
      </Typography>
      <Box mb={2} display="flex" justifyContent="flex-end">
        <Button
          startIcon={<Add />}
          variant="contained"
          onClick={() => { setEditingTable(null); setOpenTableForm(true); }}
        >
          New Table
        </Button>
      </Box>
      {modules.map((mod) => (
        <Box key={mod.id} mb={2}>
          <Box
            display="flex"
            alignItems="center"
            sx={{ cursor: "pointer", px: 1, py: 1, bgcolor: "#fafafa", borderRadius: 1 }}
            onClick={() => setOpenModuleId(openModuleId === mod.id ? null : mod.id)}
          >
            <Typography variant="h6" sx={{ flex: 1 }}>{mod.name}</Typography>
            {openModuleId === mod.id ? <ExpandLess /> : <ExpandMore />}
          </Box>
          <Collapse in={openModuleId === mod.id} timeout="auto" unmountOnExit>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Title</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell>Fields</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(tablesByModule[mod.id] || [])
                  .filter(table => table.module === mod.id || table.module_id === mod.id)
                  .map((table) => (
                    <React.Fragment key={table.id}>
                      <TableRow>
                        <TableCell>{table.title}</TableCell>
                        <TableCell>{table.description}</TableCell>
                        <TableCell>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => {
                              setCurrentTableId(table.id);
                              setEditingField(null);
                              setOpenFieldForm(true);
                            }}
                            sx={{ minWidth: 80, fontSize: 12 }}
                          >
                            Add Field
                          </Button>
                        </TableCell>
                        <TableCell>
                          <Tooltip title="Edit Table">
                            <IconButton size="small" onClick={() => { setEditingTable(table); setOpenTableForm(true); }}>
                              <Edit fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete/Archive Table">
                            <IconButton size="small" onClick={() => handleDeleteTable(table)}>
                              <Delete fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                      {/* List fields below the table row */}
                      {(fieldsByTable[table.id] || []).map((field) => (
                        <TableRow key={field.id} sx={{ bgcolor: "#f7f7fa" }}>
                          <TableCell colSpan={1} sx={{ pl: 6 }}>
                            <span style={{ fontWeight: 500 }}>{field.label}</span> <span style={{ color: "#999" }}>({field.name})</span>
                          </TableCell>
                          <TableCell colSpan={1}>{field.type}</TableCell>
                          <TableCell colSpan={1}>{field.required ? "Required" : ""}</TableCell>
                          <TableCell colSpan={1}>
                            <Tooltip title="Edit Field">
                              <IconButton
                                size="small"
                                onClick={() => {
                                  setEditingField(field);
                                  setCurrentTableId(table.id);
                                  setOpenFieldForm(true);
                                }}
                              >
                                <Edit fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete/Archive Field">
                              <IconButton size="small" onClick={() => { setCurrentTableId(table.id); handleDeleteField(field); }}>
                                <Delete fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                    </React.Fragment>
                  ))}
              </TableBody>
            </Table>
          </Collapse>
        </Box>
      ))}
      <TableForm
        open={openTableForm}
        onClose={() => { setOpenTableForm(false); setEditingTable(null); }}
        onSubmit={editingTable ? handleEditTable : handleCreateTable}
        initial={editingTable}
        modules={modules}
      />
      <FieldForm
        open={openFieldForm}
        onClose={() => { setOpenFieldForm(false); setEditingField(null); }}
        onSubmit={editingField ? handleEditField : handleCreateField}
        initial={editingField}
      />
    </Box>
  );
}