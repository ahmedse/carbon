import React, { useMemo, useState } from "react";
import { DataGrid } from "@mui/x-data-grid";
import { Button, Drawer, Box, CircularProgress, IconButton, Tooltip } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import FileCellRenderer from "./FileCellRenderer";
import DataRowFormDrawer from "./DataRowFormDrawer";
import { useNotification } from "./NotificationProvider";

function safeArray(arr) {
  return Array.isArray(arr) ? arr : [];
}

function mapRows(rows, fields) {
  const dateFields = fields.filter(f => f.type === "date").map(f => f.name);
  return rows.map(row => {
    const values = { ...row, ...row.values };
    dateFields.forEach(name => {
      if (values[name] && !(values[name] instanceof Date)) {
        try { values[name] = new Date(values[name]); } catch {}
      }
    });
    return values;
  });
}

function buildColumns(fields, editable, token, project_id, module_id, uploadRowFile, onEditRow, onDeleteRow) {
  const columns = fields.map(field => {
    const valueOptions = safeArray(field.options).map(opt =>
      typeof opt === "object"
        ? { value: opt.value, label: opt.label }
        : { value: opt, label: String(opt) }
    );

    if (field.type === "file") {
      return {
        field: field.name,
        headerName: field.label,
        width: 170,
        flex: 1,
        filterable: false,
        renderCell: params => (
          <FileCellRenderer
            value={params.value}
            rowId={params.row.id}
            fieldName={field.name}
            onChange={() => {}}
            token={token}
            project_id={project_id}
            module_id={module_id}
            uploadRowFile={uploadRowFile}
            disabled
          />
        ),
      };
    }
    if (field.type === "date") {
      return {
        field: field.name,
        headerName: field.label,
        width: 170,
        flex: 1,
        filterable: false,
        renderCell: params =>
          params.value && params.value instanceof Date
            ? params.value.toLocaleDateString()
            : params.value
            ? new Date(params.value).toLocaleDateString()
            : "",
      };
    }
    if (field.type === "boolean") {
      return {
        field: field.name,
        headerName: field.label,
        width: 120,
        flex: 1,
        filterable: false,
        renderCell: params => (
          <input type="checkbox" checked={!!params.value} readOnly />
        ),
      };
    }
    if (field.type === "select") {
      return {
        field: field.name,
        headerName: field.label,
        width: 170,
        flex: 1,
        filterable: true,
        type: "singleSelect",
        valueOptions,
      };
    }
    if (field.type === "multiselect") {
      return {
        field: field.name,
        headerName: field.label,
        width: 170,
        flex: 1,
        filterable: false,
        type: "string",
        renderCell: params => safeArray(params.value)
          .map(val => {
            const opt = valueOptions.find(o => o.value === val);
            return opt ? opt.label : val;
          }).join(", "),
      };
    }
    if (field.type === "number" || field.type === "string") {
      return {
        field: field.name,
        headerName: field.label,
        width: 170,
        flex: 1,
        filterable: true,
        type: field.type === "number" ? "number" : "string",
      };
    }
    return {
      field: field.name,
      headerName: field.label,
      width: 170,
      flex: 1,
      filterable: false,
    };
  });

  // Add actions column at end
  columns.push({
    field: "actions",
    headerName: "Actions",
    width: 120,
    sortable: false,
    filterable: false,
    renderCell: (params) => (
      <Box>
        <Tooltip title="Edit">
          <IconButton size="small" onClick={e => { e.stopPropagation(); onEditRow(params.row); }}>
            <EditIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Delete">
          <IconButton size="small" onClick={e => { e.stopPropagation(); onDeleteRow(params.row); }}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    )
  });

  return columns;
}

function FilterBar({ fields, filters, setFilters, onAddNew, onSearchChange }) {
  // Only allow filter on string, number, select fields
  const filterFields = fields.filter(
    f => ["string", "number", "select"].includes(f.type)
  );
  return (
    <div style={{ display: "flex", gap: 16, marginBottom: 8 }}>
      <input
        type="text"
        placeholder="Search..."
        value={filters._search || ""}
        onChange={e => onSearchChange(e.target.value)}
        style={{ width: 180, padding: "6px", borderRadius: 4, border: "1px solid #bbb" }}
      />
      {filterFields.map(f => {
        if (f.type === "select") {
          return (
            <select
              key={f.name}
              value={filters[f.name] ?? ""}
              onChange={e => setFilters(filters => ({ ...filters, [f.name]: e.target.value }))}
              style={{ width: 160, padding: "6px", borderRadius: 4, border: "1px solid #bbb" }}
            >
              <option value="">(All)</option>
              {(f.options || []).map(opt =>
                <option value={opt.value} key={opt.value}>{opt.label}</option>
              )}
            </select>
          );
        }
        return (
          <input
            key={f.name}
            type={f.type === "number" ? "number" : "text"}
            value={filters[f.name] ?? ""}
            placeholder={f.label}
            onChange={e => setFilters(filters => ({ ...filters, [f.name]: e.target.value }))}
            style={{ width: 140, padding: "6px", borderRadius: 4, border: "1px solid #bbb" }}
          />
        );
      })}
      <span style={{ flex: 1 }} />
      <Button variant="contained" startIcon={<AddIcon />} onClick={onAddNew}>
        Add Row
      </Button>
    </div>
  );
}

export default function DataTableGrid({
  fields,
  rows,
  filters,
  setFilters,
  token,
  project_id,
  module_id,
  uploadRowFile,
  onSelectionChange,
  onAddNew,
  onEditRow,
  onDeleteRow,
  fetchRows,
  loading,
  selected,
  onExportCsv,
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("edit");
  const [editingRow, setEditingRow] = useState(null);
  const [deleteRow, setDeleteRow] = useState(null);
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : msg?.message ?? "Notification");

  // New: Handle search in filter bar
  const handleSearchChange = (search) => {
    setFilters(f => ({ ...f, _search: search }));
  };

  // Ensure selection is updated robustly
  const handleSelectionChange = (ids) => {
    if (onSelectionChange) onSelectionChange(ids);
  };

  // Add
  const handleAddClick = () => {
    setEditingRow(null);
    setDrawerMode("add");
    setDrawerOpen(true);
  };

  // Edit (from grid action)
  const handleEditRow = (row) => {
    setEditingRow(row);
    setDrawerMode("edit");
    setDrawerOpen(true);
  };

  // Called by drawer SAVE
  const handleDrawerSave = async (values, rowId) => {
    try {
      await onEditRow(rowId, values);
      setDrawerOpen(false);
      setEditingRow(null);
      notify({ message: rowId ? "Row updated" : "Row added", type: "success" });
      fetchRows?.();
    } catch (err) {
      notify({ message: err?.message || "Failed to save row", type: "error" });
    }
  };

  // Delete (from grid action)
  const handleDeleteRow = (row) => {
    setDeleteRow(row);
  };

  // Confirm row delete
  const handleConfirmDelete = async () => {
    try {
      await onDeleteRow(deleteRow);
      notify({ message: "Row deleted", type: "success" });
      fetchRows?.();
    } catch (err) {
      notify({ message: err?.message || "Failed to delete row", type: "error" });
    }
    setDeleteRow(null);
  };

  const columns = useMemo(
    () => buildColumns(fields, false, token, project_id, module_id, uploadRowFile, handleEditRow, handleDeleteRow),
    [fields, token, project_id, module_id, uploadRowFile]
  );
  console.log("rows in DataTableGrid", rows);
  const mappedRows = useMemo(
    () => mapRows(rows.filter(row => row && row.id), fields),
    [rows, fields]
  );

  return (
    <div style={{ width: "100%", minHeight: 600, position: "relative" }}>
      <FilterBar
        fields={fields}
        filters={filters}
        setFilters={setFilters}
        onAddNew={handleAddClick}
        onSearchChange={handleSearchChange}
      />

      {/* Bulk actions always visible when selection exists */}
      {selected && selected.length > 0 && (
        <Box mb={2}>
          {/*
            You can render your BulkActionBar here.
            Example:
            <BulkActionBar selected={selected} onDelete={...} onExport={...} />
          */}
        </Box>
      )}

      <div style={{ position: "relative" }}>
        <DataGrid
          autoHeight
          rows={mappedRows}
          columns={columns}
          checkboxSelection
          disableSelectionOnClick
          editMode="none"
          onRowSelectionModelChange={handleSelectionChange}
          getRowId={row => row.id}
          pageSize={20}
          rowsPerPageOptions={[20, 50, 100]}
          sx={{
            bgcolor: "#fff",
            borderRadius: 2,
            boxShadow: 1,
            opacity: loading ? 0.4 : 1,
            pointerEvents: loading ? "none" : "auto"
          }}
        />
        {loading && (
          <Box
            sx={{
              position: "absolute",
              inset: 0,
              bgcolor: "rgba(255,255,255,0.5)",
              zIndex: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}
          >
            <CircularProgress />
          </Box>
        )}
      </div>

      {/* Drawer for add/edit */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setEditingRow(null); }}
        PaperProps={{
          sx: { width: { xs: "100%", sm: 500 }, pt: { xs: 7, sm: 9 } }
        }}
      >
        <Box p={2}>
          <DataRowFormDrawer
            open
            onClose={() => { setDrawerOpen(false); setEditingRow(null); }}
            fields={fields}
            initial={drawerMode === "edit" ? editingRow : null}
            onSubmit={handleDrawerSave}
            token={token}
            project_id={project_id}
            module_id={module_id}
            uploadRowFile={uploadRowFile}
            rowId={editingRow?.id}
            mode={drawerMode}
          />
        </Box>
      </Drawer>

      {/* Confirm row delete */}
      <Drawer
        anchor="right"
        open={!!deleteRow}
        onClose={() => setDeleteRow(null)}
        PaperProps={{ sx: { width: { xs: "100%", sm: 400 }, pt: { xs: 7, sm: 9 } } }}
      >
        <Box p={3}>
          <div style={{ fontWeight: 600, fontSize: 18, marginBottom: 16 }}>Delete Row</div>
          <div>Are you sure you want to delete this row?</div>
          <Box mt={2} display="flex" gap={2}>
            <Button onClick={() => setDeleteRow(null)}>Cancel</Button>
            <Button onClick={handleConfirmDelete} color="error" variant="contained">
              Delete
            </Button>
          </Box>
        </Box>
      </Drawer>
    </div>
  );
}