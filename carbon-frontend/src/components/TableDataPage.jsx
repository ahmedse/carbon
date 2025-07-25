// File: src/components/TableDataPage.jsx

import React, { useEffect, useState, useCallback } from "react";
import { Box, Typography } from "@mui/material";
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
        const safeRows = Array.isArray(data) ? data : [];
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

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        {table?.title}
      </Typography>

      <BulkActionBar
        selected={selected}
        onDelete={handleBulkDelete}
        onExport={handleExport}
      />

      <DataTableGrid
        fields={fields}
        rows={rows}
        filters={filters}
        setFilters={handleSetFilters}
        onSelectionChange={setSelected}
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
    </Box>
  );
}