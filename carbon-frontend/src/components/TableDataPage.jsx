// File: src/components/TableDataPage.jsx

import React, { useEffect, useState, useCallback } from "react";
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions, Divider, Chip } from "@mui/material";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import {
  fetchDataSchemaTables,
  fetchDataSchemaFields,
  fetchDataRows,
  createDataRow,
  updateDataRow,
  deleteDataRow,
  bulkDeleteDataRows,
  exportRowsToCsv,
  uploadRowFile
} from "../api/dataschema";
import DataTableGrid from "./DataTableGrid";
import BulkActionBar from "./BulkActionBar";
import EvidenceUploader from "./evidence/EvidenceUploader";
import EvidenceViewer from "./evidence/EvidenceViewer";
import { useNotification } from "./NotificationProvider";

/**
 * TableDataPage
 * @param {string} project_id - always required, for RBAC and queries
 * @param {string} module_id - required for module-level tables
 * @param {string} moduleId - for display/legacy (same as module_id)
 * @param {string} tableId
 * @param {string} lang
 * @param {string} token
 */
export default function TableDataPage({
  project_id,
  module_id,
  moduleId,
  tableId,
  lang,
  token
}) {
  const [fields, setFields] = useState([]);
  const [table, setTable] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({});
  const [selected, setSelected] = useState([]);
  const [selectedRowId, setSelectedRowId] = useState(null);
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);
  const [evidenceRefreshKey, setEvidenceRefreshKey] = useState(0);

  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));

  // Helper to handle and notify all errors
  function handleError(err, defaultMsg) {
    // Log all error details for developers
    console.error("[TableDataPage] Error:", err);

    // User-friendly, respectful notification
    if (
      err?.message?.toLowerCase().includes("permission") ||
      err?.message?.includes("403") ||
      err?.detail?.toLowerCase?.().includes("permission")
    ) {
      notify({
        message:
          "You do not have permission to perform this action. If you believe this is an error, please contact your administrator.",
        type: "error",
      });
    } else if (
      err?.message?.includes("NetworkError") ||
      err?.message?.includes("Failed to fetch") ||
      err?.message?.includes("Network error")
    ) {
      notify({
        message:
          "Could not connect to the server. Please check your internet connection or try again later.",
        type: "error",
      });
    } else {
      notify({
        message:
          err?.message ||
          err?.detail ||
          defaultMsg ||
          "An error occurred. Please try again or contact support.",
        type: "error",
      });
    }
  }

  // Defensive: ensure fetches are always safe
  const fetchRows = useCallback(() => {
    setLoading(true);
   fetchDataRows(token, tableId, filters, project_id, module_id)
      .then((data) => {
        const safeRows = (Array.isArray(data) ? data : []).filter(
          row => row && row.id && typeof row.id !== "undefined"
        );
        setRows(safeRows);
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
        handleError(err, "Failed to fetch rows");
      });
  }, [token, tableId, filters, project_id, module_id]);

  // Fetch schema on mount
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchDataSchemaTables(token, project_id, module_id).then((tables) =>
        (tables || []).find((t) => String(t.id) === String(tableId))
      ),
      fetchDataSchemaFields(token, tableId, project_id, module_id),
    ])
      .then(([table, fields]) => {
        setTable(table);
        setFields(fields || []);
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
        handleError(err, "Failed to fetch schema");
      });
    // eslint-disable-next-line
  }, [tableId, moduleId, module_id, project_id, token]);

  useEffect(() => {
    if (table) fetchRows();
    // eslint-disable-next-line
  }, [table, fetchRows]);

  // Bulk delete
  const handleBulkDelete = async () => {
    setLoading(true);
    try {
      await bulkDeleteDataRows(token, selected, project_id, module_id);
      setSelected([]);
      fetchRows();
      notify({ message: "Rows deleted.", type: "success" });
    } catch (err) {
      handleError(err, "Bulk delete failed");
      setLoading(false);
    }
  };

  // Bulk export
  const handleExport = () => {
    try {
      const exportRows = selected.length
        ? rows.filter((row) => selected.includes(row.id))
        : rows;
      exportRowsToCsv(exportRows, fields);
      notify({ message: "Exported to CSV.", type: "success" });
    } catch (err) {
      handleError(err, "CSV export failed");
    }
  };

  // Add/Edit Row
  const handleEditRow = async (idOrNull, values) => {
    setLoading(true);
    try {
      const data_table = values.data_table || tableId;
      const rowValues = values.values || values;
      if (!idOrNull) {
        await createDataRow(token, rowValues, data_table, project_id, module_id);
        notify({ message: "Row added.", type: "success" });
      } else {
        await updateDataRow(token, idOrNull, { values: rowValues }, project_id, module_id, true);
        notify({ message: "Row updated.", type: "success" });
      }
      fetchRows();
    } catch (err) {
      handleError(err, "Failed to save row");
      setLoading(false);
    }
  };

  // Single row delete
  const handleDeleteRow = async (row) => {
    if (!row?.id) return;
    setLoading(true);
    try {
      await deleteDataRow(token, row.id, project_id, module_id);
      fetchRows();
      notify({ message: "Row deleted.", type: "success" });
    } catch (err) {
      handleError(err, "Failed to delete row");
      setLoading(false);
    }
  };

  // Filter handler - triggers grid refresh
  const handleSetFilters = (newFilters) => {
    setFilters(newFilters);
    // fetchRows will be triggered by useEffect on filters change
  };

  // Row selection handler - track selected row IDs
  const handleRowSelection = (rowIds) => {
    setSelected(rowIds);
    if (rowIds.length === 1) {
      setSelectedRowId(rowIds[0]);
    } else {
      setSelectedRowId(null);
    }
  };

  return (
    <Box>
      <Typography variant="h5" fontWeight={600} sx={{ mb: 2 }}>
        {table?.title}
      </Typography>

      <BulkActionBar
        selected={selected}
        onDelete={handleBulkDelete}
        onExport={handleExport}
      />

      <Button
        startIcon={<AttachFileIcon />}
        onClick={() => setShowEvidenceModal(true)}
        disabled={!selectedRowId || selected.length !== 1}
        variant="outlined"
        size="small"
        sx={{ ml: 1, mb: 2 }}
      >
        Evidence
      </Button>

      <DataTableGrid
        fields={fields}
        rows={rows}
        filters={filters}
        setFilters={handleSetFilters}
        onSelectionChange={setSelected}
        onRowSelectionModelChange={handleRowSelection}
        checkboxSelection
        token={token}
        project_id={project_id}
        module_id={module_id}
        uploadRowFile={uploadRowFile}
        fetchRows={fetchRows}
        editable={false}
        onEditRow={handleEditRow}
        onDeleteRow={handleDeleteRow}
        loading={loading}
        selected={selected}
        BulkActionBar={null}
        onExportCsv={handleExport}
        onAddNew={null}
      />

      <Dialog
        open={showEvidenceModal}
        onClose={(event, reason) => {
          if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
            return;
          }
          setShowEvidenceModal(false);
        }}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            minHeight: '60vh',
            maxHeight: '90vh',
            resize: 'both',
            overflow: 'auto'
          }
        }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">Evidence Attachments</Typography>
            <Chip label={`Row ID: ${selectedRowId}`} size="small" color="primary" variant="outlined" />
          </Box>
        </DialogTitle>
        
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Upload supporting documents (invoices, receipts, photos, etc.) for audit verification.
          </Typography>
          
          <Box sx={{ mt: 2 }}>
            <EvidenceUploader
              dataRowId={selectedRowId}
              token={token}
              onUploadComplete={() => setEvidenceRefreshKey(prev => prev + 1)}
            />
          </Box>
          
          <Divider sx={{ my: 3 }} />
          
          <Typography variant="subtitle1" gutterBottom>Attached Evidence</Typography>
          
          <EvidenceViewer
            dataRowId={selectedRowId}
            token={token}
            key={evidenceRefreshKey}
            onDelete={() => setEvidenceRefreshKey(prev => prev + 1)}
          />
        </DialogContent>
        
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setShowEvidenceModal(false)} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}