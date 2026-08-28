// File: src/components/TableDataPage.jsx

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Box, Typography, Button } from "@mui/material";
import { useTranslation } from "react-i18next";
import UploadIcon from "@mui/icons-material/Upload";
import DownloadIcon from "@mui/icons-material/Download";
import { API_BASE_URL } from "../config";
import { authFetch } from "../api/api";
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
import BulkImportWizard from "./import/BulkImportWizard";
import { useNotification } from "./NotificationProvider";
import useDocumentTitle from "../hooks/useDocumentTitle";

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
  _lang,
  token
}) {
  const { t } = useTranslation('common');
  useDocumentTitle(t("tableDataTitle"));

  const [fields, setFields] = useState([]);
  const [table, setTable] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({});
  const [selected, setSelected] = useState([]);
  const [showImportWizard, setShowImportWizard] = useState(false);

  const notifyCtx = useNotification();
  const notify = useMemo(
    () => typeof notifyCtx?.notify === "function"
      ? notifyCtx.notify
      : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification")),
    [notifyCtx?.notify]
  );

  // Helper to handle and notify all errors
  const handleError = useCallback((err, defaultMsg) => {
    // Log all error details for developers
    console.error("[TableDataPage] Error:", err);

    // User-friendly, respectful notification
    if (
      err?.message?.toLowerCase().includes("permission") ||
      err?.message?.includes("403") ||
      err?.detail?.toLowerCase?.().includes("permission")
    ) {
      notify({
        message: t("permissionDeniedMsg"),
        type: "error",
      });
    } else if (
      err?.message?.includes("NetworkError") ||
      err?.message?.includes("Failed to fetch") ||
      err?.message?.includes("Network error")
    ) {
      notify({
        message: t("networkErrorMsg"),
        type: "error",
      });
    } else {
      notify({
        message:
          err?.message ||
          err?.detail ||
          defaultMsg ||
          t("genericErrorMsg"),
        type: "error",
      });
    }
  }, [notify, t]);

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
        handleError(err, t("failedFetchRows"));
      });
  }, [token, tableId, filters, project_id, module_id, handleError, t]);

  // Fetch schema on mount
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchDataSchemaTables(token, project_id, module_id).then((tables) => {
        const list = Array.isArray(tables) ? tables : tables?.results || [];
        return list.find((t) => String(t.id) === String(tableId));
      }),
      fetchDataSchemaFields(token, tableId, project_id, module_id),
    ])
      .then(([table, fields]) => {
        setTable(table);
        setFields(Array.isArray(fields) ? fields : fields?.results || []);
        setLoading(false);
      })
      .catch((err) => {
        setLoading(false);
        handleError(err, t("failedFetchSchema"));
      });
    // eslint-disable-next-line
  }, [tableId, moduleId, module_id, project_id, token, t]);

  useEffect(() => {
    if (table) fetchRows();
     
  }, [table, fetchRows]);

  // Bulk delete
  const handleBulkDelete = async () => {
    setLoading(true);
    try {
      await bulkDeleteDataRows(token, selected, project_id, module_id);
      setSelected([]);
      fetchRows();
      notify({ message: t("rowsDeleted"), type: "success" });
    } catch (err) {
      handleError(err, t("bulkDeleteFailed"));
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
      notify({ message: t("exportedToCsv"), type: "success" });
    } catch (err) {
      handleError(err, t("csvExportFailed"));
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
        notify({ message: t("rowAdded"), type: "success" });
      } else {
        await updateDataRow(token, idOrNull, { values: rowValues }, project_id, module_id, true);
        notify({ message: t("rowUpdated"), type: "success" });
      }
      fetchRows();
    } catch (err) {
      handleError(err, t("failedSaveRow"));
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
      notify({ message: t("rowDeleted"), type: "success" });
    } catch (err) {
      handleError(err, t("failedDeleteRow"));
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
  };

  // Handle import completion
  const handleImportComplete = (result) => {
    if (result.created > 0 && result.failed === 0) {
      notify({
        message: t("importSuccess", { count: result.created }),
        type: "success",
      });
    } else if (result.created > 0 && result.failed > 0) {
      notify({
        message: t("importWithErrors", { count: result.created, errors: result.failed }),
        type: "warning",
      });
      console.warn("[BulkImport] Errors:", result.errors);
    } else {
      notify({
        message: t("importFailedCount", { count: result.failed }),
        type: "error",
      });
      console.error("[BulkImport] Errors:", result.errors);
    }
    fetchRows();
    setShowImportWizard(false);
  };

  // Handle template download
  const handleDownloadTemplate = async () => {
    try {
      const includeExample = window.confirm(t("confirmTemplateExample"));
      const endpoint = `datarows/download-template/?data_table=${tableId}&include_example=${includeExample}`;
      
      const response = await authFetch(endpoint, {
        method: 'GET',
        token,
        project_id,
        module_id,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `${table?.name || 'template'}_template.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);

      notify({
        message: t("templateDownloaded"),
        type: "success",
      });
    } catch (err) {
      handleError(err, t("failedDownloadTemplate"));
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

      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <Button
          startIcon={<UploadIcon />}
          onClick={() => setShowImportWizard(true)}
          variant="contained"
          size="small"
        >
          {t("bulkImport")}
        </Button>

        <Button
          startIcon={<DownloadIcon />}
          onClick={handleDownloadTemplate}
          variant="outlined"
          size="small"
        >
          {t("downloadTemplate")}
        </Button>
      </Box>

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
        tableId={tableId}
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

      <BulkImportWizard
        open={showImportWizard}
        onClose={() => setShowImportWizard(false)}
        tableId={tableId}
        fields={fields}
        token={token}
        onImportComplete={handleImportComplete}
      />
    </Box>
  );
}