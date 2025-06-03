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


export default function TableDataPage({ moduleId, tableId, lang, token, context_id }) {
  const [fields, setFields] = useState([]);
  const [table, setTable] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({});
  const [selected, setSelected] = useState([]);
  // const notify = useNotification();

  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));

  // Defensive: ensure fetches are always safe
  const fetchRows = useCallback(() => {
    setLoading(true);
    fetchDataRows(token, tableId, filters, context_id)
      .then(data => {
        // Defensive: always use an array
        const safeRows = Array.isArray(data) ? data : [];
        setRows(safeRows);
        setLoading(false);
      })
      .catch(err => {
        setLoading(false);
        notify({ message: err?.message || "Failed to fetch rows", type: "error" });
      });
  }, [token, tableId, filters, context_id, notify]);

  // Fetch schema on mount
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchDataSchemaTables(token, context_id, moduleId).then(tables =>
        (tables || []).find(t => String(t.id) === String(tableId))
      ),
      fetchDataSchemaFields(token, tableId, context_id)
    ]).then(([table, fields]) => {
      setTable(table);
      setFields(fields || []);
      setLoading(false);
    }).catch(err => {
      setLoading(false);
      notify({ message: err?.message || "Failed to fetch schema", type: "error" });
    });
    // eslint-disable-next-line
  }, [tableId, moduleId, token, context_id]);

  useEffect(() => {
    if (table) fetchRows();
    // eslint-disable-next-line
  }, [table, fetchRows]);

  // Bulk delete
  const handleBulkDelete = async () => {
    setLoading(true);
    try {
      await bulkDeleteDataRows(token, selected, context_id);
      setSelected([]);
      fetchRows();
      notify({ message: "Rows deleted.", type: "success" });
    } catch (err) {
      notify({ message: err?.message || "Bulk delete failed", type: "error" });
      setLoading(false);
    }
  };

  // Bulk export
  const handleExport = () => {
    try {
      const exportRows = selected.length
        ? rows.filter(row => selected.includes(row.id))
        : rows;
      exportRowsToCsv(exportRows, fields);
      notify({ message: "Exported to CSV.", type: "success" });
    } catch (err) {
      notify({ message: err?.message || "CSV export failed", type: "error" });
    }
  };

  // Add/Edit Row
  const handleEditRow = async (idOrNull, values) => {
    setLoading(true);
    try {
      const data_table = values.data_table || tableId;
      const rowValues = values.values || values;
      if (!idOrNull) {
        await createDataRow(token, rowValues, data_table, context_id);
        notify({ message: "Row added.", type: "success" });
      } else {
        await updateDataRow(token, idOrNull, { values: rowValues }, context_id, true);
        notify({ message: "Row updated.", type: "success" });
      }
      fetchRows();
    } catch (err) {
      notify({ message: err?.message || "Failed to save row", type: "error" });
      setLoading(false);
    }
  };

  // Single row delete
  const handleDeleteRow = async (row) => {
    if (!row?.id) return;
    setLoading(true);
    try {
      await deleteDataRow(token, row.id, context_id);
      fetchRows();
      notify({ message: "Row deleted.", type: "success" });
    } catch (err) {
      notify({ message: err?.message || "Failed to delete row", type: "error" });
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
        context_id={context_id}
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