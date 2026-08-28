// File: src/components/BulkActionBar.jsx

import React, { useState } from "react";
import { Box, Button, CircularProgress } from "@mui/material";
import { useTranslation } from "react-i18next";
import { useNotification } from "./NotificationProvider";
export default function BulkActionBar({ selected, onDelete, onExport }) {
  const { t } = useTranslation('common');
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));

  if (!selected?.length) return null;

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await onDelete?.();
      notify({ message: t("bulkRowsDeleted"), type: "success" });
    } catch (err) {
      notify({ message: err?.message || t("bulkDeleteFailed"), type: "error" });
    }
    setDeleting(false);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      await onExport?.();
      notify({ message: t("csvExported"), type: "success" });
    } catch (err) {
      notify({ message: err?.message || t("csvExportFailed"), type: "error" });
    }
    setExporting(false);
  };

  return (
    <Box display="flex" gap={2} mb={2} alignItems="center">
      <Button
        color="error"
        variant="outlined"
        onClick={handleDelete}
        disabled={deleting}
        startIcon={deleting ? <CircularProgress color="inherit" size={18} /> : null}
        aria-label={t("deleteSelectedAria")}
      >
        {t("deleteSelected")}
      </Button>
      <Button
        variant="outlined"
        onClick={handleExport}
        disabled={exporting}
        startIcon={exporting ? <CircularProgress color="inherit" size={18} /> : null}
        aria-label={t("exportSelectedAria")}
      >
        {t("exportCsv")}
      </Button>
      <Box flex={1} />
      <span aria-live="polite">{t("selectedCount", { count: selected.length })}</span>
    </Box>
  );
}