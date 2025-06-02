import React, { useEffect, useState, useCallback } from "react";
import {
  Box, Typography, IconButton, Button, CircularProgress, Tooltip, TextField, MenuItem
} from "@mui/material";
import { Add, Edit, Delete, TableRows } from "@mui/icons-material";
import { DataGrid } from "@mui/x-data-grid";
import { useAuth } from "../auth/AuthContext";
import { fetchModules } from "../api/modules";
import {
  fetchDataSchemaTables, createDataSchemaTable, updateDataSchemaTable, deleteDataSchemaTable,
  fetchDataSchemaFields, createDataSchemaField, updateDataSchemaField, deleteDataSchemaField,
  updateDataSchemaFieldOrder
} from "../api/dataschema";
import TableFormDrawer from "../components/TableFormDrawer";
import FieldManagerDrawer from "../components/FieldManagerDrawer";

export default function TableManagerPage() {
  const { user, currentContext } = useAuth();
  const lang = "en";
  const [modules, setModules] = useState([]);
  const [tablesByModule, setTablesByModule] = useState({});
  const [fieldsByTable, setFieldsByTable] = useState({});
  const [loading, setLoading] = useState(true);

  // UI state
  const [openTableDrawer, setOpenTableDrawer] = useState(false);
  const [editingTable, setEditingTable] = useState(null);
  const [openFieldDrawer, setOpenFieldDrawer] = useState(false);
  const [editingFieldsTableId, setEditingFieldsTableId] = useState(null);
  const [search, setSearch] = useState("");
  const [moduleFilter, setModuleFilter] = useState(localStorage.getItem("moduleFilter") || "");

  const validModuleFilterIds = modules.map(m => String(m.id));
  const safeModuleFilter =
    moduleFilter === "" || validModuleFilterIds.includes(String(moduleFilter))
      ? moduleFilter
      : "";

  // --- Refetch all modules, tables, and fields ---
  const refetchAll = useCallback(() => {
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

  // --- Initial load ---
  useEffect(() => {
    if (!user || !currentContext) return;
    refetchAll();
  }, [user, currentContext, refetchAll]);

  // --- Persist module filter ---
  const handleModuleFilterChange = (value) => {
    setModuleFilter(value);
    localStorage.setItem("moduleFilter", value);
  };

  // --- Only include tables that actually belong to the module ---
  const allTables = [];
  modules.forEach(mod => {
    (tablesByModule[mod.id] || []).forEach(table => {
      if (
        (table.module && (table.module === mod.id || table.module === mod.name || table.module === mod.slug)) ||
        (table.module_id && table.module_id === mod.id)
      ) {
        allTables.push({
          ...table,
          moduleName: mod.name,
          moduleId: mod.id,
          id: table.id // id must be unique!
        });
      }
    });
  });

  // --- Apply search and filter ---
  const filteredTables = allTables.filter(table =>
    (!moduleFilter || String(table.moduleId) === String(moduleFilter)) &&
    (
      (table.title || "").toLowerCase().includes(search.toLowerCase()) ||
      (table.description || "").toLowerCase().includes(search.toLowerCase())
    )
  );

  // --- DataGrid columns ---
  const columns = [
    { field: "title", headerName: "Title", flex: 1, minWidth: 180 },
    { field: "moduleName", headerName: "Module", flex: 1, minWidth: 120 },
    { field: "description", headerName: "Description", flex: 2, minWidth: 200 },
    {
      field: "row_count",
      headerName: "Rows",
      width: 80,
      type: "number"
    },
    {
      field: "actions",
      headerName: "Actions",
      width: 200,
      sortable: false,
      renderCell: (params) => {
        const hasData = params.row.row_count > 0;
        return (
          <Box display="flex" gap={1}>
            <Tooltip title={hasData ? "Cannot edit fields: table has data" : "Manage Fields"}>
              <span>
                <IconButton
                  size="small"
                  color="primary"
                  disabled={hasData}
                  onClick={() => {
                    setEditingFieldsTableId(params.row.id);
                    setOpenFieldDrawer(true);
                  }}
                >
                  <TableRows />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Edit Table">
              <IconButton
                size="small"
                color="info"
                onClick={() => {
                  setEditingTable(params.row);
                  setOpenTableDrawer(true);
                }}
              >
                <Edit fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={hasData ? "Cannot delete: table has data" : "Delete/Archive Table"}>
              <span>
                <IconButton
                  size="small"
                  color="error"
                  disabled={hasData}
                  onClick={() => handleDeleteTable(params.row)}
                >
                  <Delete fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        );
      }
    }
  ];

  // --- Table CRUD ---
  const handleCreateTable = async (data) => {
    await createDataSchemaTable(user.token, data, currentContext.context_id);
    setOpenTableDrawer(false);
    setEditingTable(null);
    refetchAll();
  };

  const handleEditTable = async (data) => {
    await updateDataSchemaTable(user.token, editingTable.id, { ...editingTable, ...data }, currentContext.context_id);
    setOpenTableDrawer(false);
    setEditingTable(null);
    refetchAll();
  };

  const handleDeleteTable = async (table) => {
    if (!window.confirm(`Archive table "${table.title}"?`)) return;
    await deleteDataSchemaTable(user.token, table.id, currentContext.context_id);
    refetchAll();
  };

  // --- Field CRUD ---
  const handleAddField = async (data) => {
    await createDataSchemaField(user.token, { ...data, data_table: editingFieldsTableId }, currentContext.context_id);
    refetchAll();
  };
  const handleEditField = async (oldField, data) => {
    await updateDataSchemaField(user.token, oldField.id, { ...oldField, ...data }, currentContext.context_id);
    refetchAll();
  };
  const handleDeleteField = async (field) => {
    if (!window.confirm(`Archive field "${field.label}"?`)) return;
    await deleteDataSchemaField(user.token, field.id, currentContext.context_id);
    refetchAll();
  };
  const handleSaveFieldOrder = async (fields) => {
    await updateDataSchemaFieldOrder(user.token, editingFieldsTableId, fields, currentContext.context_id);
    refetchAll();
  };

  if (loading) return <CircularProgress sx={{ m: 4 }} />;

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        Data Schema Manager <span style={{ fontWeight: 400, fontSize: 18, color: "#888" }}>(Define Data Tables)</span>
      </Typography>
      <Box display="flex" gap={2} mb={2} alignItems="center">
        <TextField
          select
          label="Module"
          value={moduleFilter}
          onChange={e => handleModuleFilterChange(e.target.value)}
          sx={{ minWidth: 180 }}
        >
          <MenuItem value="">All Modules</MenuItem>
          {modules.map(mod => (
            <MenuItem key={mod.id} value={mod.id}>{mod.name}</MenuItem>
          ))}
        </TextField>
        <TextField
          label="Search"
          value={search}
          onChange={e => setSearch(e.target.value)}
          sx={{ minWidth: 220 }}
        />
        <Box flex={1} />
        <Button
          startIcon={<Add />}
          variant="contained"
          onClick={() => { setEditingTable(null); setOpenTableDrawer(true); }}
        >
          New Table
        </Button>
      </Box>
      <DataGrid
        autoHeight
        rows={filteredTables}
        columns={columns}
        pageSize={10}
        rowsPerPageOptions={[10, 20, 50]}
        disableSelectionOnClick
        sx={{
          bgcolor: "#fff",
          borderRadius: 2,
          boxShadow: 1,
          mb: 4
        }}
        getRowId={row => row.id}
      />
      <TableFormDrawer
        open={openTableDrawer}
        onClose={() => { setOpenTableDrawer(false); setEditingTable(null); }}
        onSubmit={editingTable ? handleEditTable : handleCreateTable}
        initial={editingTable}
        modules={modules}
        lang={lang}
        // --- Fix for top bar overlap ---
        PaperProps={{ sx: { mt: { xs: '56px', sm: '64px' } } }}
      />
      <FieldManagerDrawer
        open={openFieldDrawer}
        onClose={() => setOpenFieldDrawer(false)}
        fields={fieldsByTable[editingFieldsTableId] || []}
        onSaveOrder={handleSaveFieldOrder}
        onEditField={handleEditField}
        onAddField={handleAddField}
        onDeleteField={handleDeleteField}
        lang={lang}
        // --- Fix for top bar overlap ---
        PaperProps={{ sx: { mt: { xs: '56px', sm: '64px' } } }}
      />
    </Box>
  );
}