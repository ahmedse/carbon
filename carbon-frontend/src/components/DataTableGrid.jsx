import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataGrid } from "@mui/x-data-grid";
import { Button, Dialog, Box, CircularProgress, IconButton, Tooltip, DialogTitle, DialogContent, DialogActions, Typography, Chip, useTheme } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import VisibilityIcon from "@mui/icons-material/Visibility";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import FileCellRenderer from "./FileCellRenderer";
import DataRowFormDrawer from "./DataRowFormDrawer";
import { useNotification } from "./NotificationProvider";

function safeArray(arr) {
  if (Array.isArray(arr)) return arr;
  if (typeof arr === 'string') {
    try { return JSON.parse(arr); } catch { return []; }
  }
  return [];
}

function mapRows(rows, fields) {
  const dateFields = fields.filter(f => f.type === "date").map(f => f.name);
  return rows.map(row => {
    const values = { ...row, ...row.values };
    dateFields.forEach(name => {
      if (values[name] && !(values[name] instanceof Date)) {
        try { values[name] = new Date(values[name]); } catch { /* ignore */ }
      }
    });
    return values;
  });
}

function ActionCellComponent({ row, onDeleteRow, tableId, rowId }) {
  const navigate = useNavigate();

  const handleViewRow = () => {
    // tableId prop is passed from DataTableGrid; row.data_table is the API field name
    const effectiveTableId = tableId || row.data_table || row.table_id;
    const effectiveRowId = rowId || row.id;
    if (effectiveTableId && effectiveRowId) {
      navigate(`/carbon/data-entry/row/${effectiveTableId}/${effectiveRowId}`);
    }
  };

  return (
    <Box sx={{ display: 'flex', gap: 0.5 }}>
      <Tooltip title="View Details">
        <IconButton size="small" onClick={e => { e.stopPropagation(); handleViewRow(); }}>
          <VisibilityIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Delete">
        <IconButton size="small" onClick={e => { e.stopPropagation(); onDeleteRow(row); }}>
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}

function buildColumns(fields, editable, token, project_id, module_id, uploadRowFile, onEditRow, onDeleteRow, tableId) {
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

  // Add evidence column (if evidence exists)
  columns.push({
    field: "evidence_count",
    headerName: "Evidence",
    width: 100,
    sortable: false,
    filterable: false,
    renderCell: (params) => {
      const evidenceCount = params.row.evidence_count || 0;
      if (evidenceCount === 0) return null;
      return (
        <Chip
          icon={<AttachFileIcon />}
          label={evidenceCount}
          size="small"
          variant="outlined"
        />
      );
    }
  });

  // Add actions column at end
  columns.push({
    field: "actions",
    headerName: "Actions",
    width: 160,
    sortable: false,
    filterable: false,
    renderCell: (params) => (
      <ActionCellComponent
        row={params.row}
        onDeleteRow={onDeleteRow}
        tableId={tableId || params.row.data_table || params.row.table_id}
        rowId={params.row.id}
      />
    )
  });

  return columns;
}

function FilterBar({ fields, filters, setFilters, onAddNew, onSearchChange }) {
  const theme = useTheme();
  const filterFields = fields.filter(
    f => ["string", "number", "select"].includes(f.type)
  );
  
  const inputStyle = {
    padding: "8px 12px",
    borderRadius: 6,
    border: `1px solid ${theme.palette.divider}`,
    fontSize: "0.8125rem",
    outline: "none",
    transition: "border-color 0.15s",
  };
  
  return (
    <div style={{ 
      display: "flex", 
      gap: 12, 
      marginBottom: 16, 
      padding: "12px 0",
      flexWrap: "wrap",
      alignItems: "center"
    }}>
      <input
        type="text"
        placeholder="Search..."
        value={filters._search || ""}
        onChange={e => onSearchChange(e.target.value)}
        style={{ ...inputStyle, width: 200 }}
      />
      {filterFields.map(f => {
        if (f.type === "select") {
          return (
            <select
              key={f.name}
              value={filters[f.name] ?? ""}
              onChange={e => setFilters(filters => ({ ...filters, [f.name]: e.target.value }))}
              style={{ ...inputStyle, width: 150, cursor: "pointer" }}
            >
              <option value="">{f.label}</option>
              {safeArray(f.options).map(opt =>
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
            style={{ ...inputStyle, width: 130 }}
          />
        );
      })}
      <span style={{ flex: 1 }} />
      <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={onAddNew}>
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
  tableId,
  uploadRowFile,
  onSelectionChange,
  onRowSelectionModelChange,
  onAddNew: _onAddNew,
  onEditRow,
  onDeleteRow,
  fetchRows,
  loading,
  selected,
  onExportCsv: _onExportCsv,
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
    if (onRowSelectionModelChange) onRowSelectionModelChange(ids);
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
    () => buildColumns(fields, false, token, project_id, module_id, uploadRowFile, handleEditRow, handleDeleteRow, tableId),
    [fields, token, project_id, module_id, uploadRowFile, tableId]
  );
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

      <div style={{ position: "relative", height: '100%' }}>
        <DataGrid
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
            bgcolor: 'background.paper',
            borderRadius: 2,
            boxShadow: 1,
            opacity: loading ? 0.4 : 1,
            pointerEvents: loading ? "none" : "auto",
            height: '100%',
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

      {/* Dialog for add/edit (Modal, not closeable by backdrop click) */}
      <Dialog
        open={drawerOpen}
        onClose={(_event, _reason) => {
          // Only close on explicit button click, not backdrop or escape
          return;
        }}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            minHeight: '60vh',
            maxHeight: '90vh',
            resize: 'both',
            overflow: 'auto',
            display: 'flex',
            flexDirection: 'column'
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}>
          <span>{drawerMode === 'edit' ? 'Edit Row' : 'Add New Row'}</span>
          <IconButton
            edge="end"
            color="inherit"
            onClick={() => { setDrawerOpen(false); setEditingRow(null); }}
            sx={{ p: 0.5 }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        
        <DialogContent sx={{ flex: 1, overflow: 'auto', pb: 2 }}>
          <Box sx={{ pt: 1 }}>
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
        </DialogContent>
        
        <DialogActions sx={{ px: 2, py: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
          <Button onClick={() => { setDrawerOpen(false); setEditingRow(null); }} variant="outlined">
            Cancel
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirm row delete (Modal Dialog) */}
      <Dialog
        open={!!deleteRow}
        onClose={(_event, _reason) => {
          // Only close on explicit button click
          return;
        }}
        maxWidth="xs"
        fullWidth
        PaperProps={{
          sx: {
            minHeight: 'auto'
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Delete Row</span>
          <IconButton
            edge="end"
            color="inherit"
            onClick={() => setDeleteRow(null)}
            sx={{ p: 0.5 }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        
        <DialogContent>
          <Typography>Are you sure you want to delete this row? This action cannot be undone.</Typography>
        </DialogContent>
        
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setDeleteRow(null)} variant="outlined">
            Cancel
          </Button>
          <Button onClick={handleConfirmDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}