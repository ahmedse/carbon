// File: src/components/FileCellRenderer.jsx

import React, { useRef, useState } from "react";
import { Box, IconButton, Link, CircularProgress, Tooltip } from "@mui/material";
import { AttachFile, Delete, CloudUpload } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useNotification } from "./NotificationProvider";

export default function FileCellRenderer({
  value, onChange, disabled, rowId, fieldName, uploadRowFile, token, context_id
}) {
  const { t } = useTranslation('common');
  const fileInputRef = useRef();
  const [uploading, setUploading] = useState(false);
  const notifyCtx = useNotification();
  const notify = typeof notifyCtx?.notify === "function"
    ? notifyCtx.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!rowId) {
      notify({ message: t("saveRowFirst"), type: "error" });
      return;
    }
    setUploading(true);
    try {
      const uploaded = await uploadRowFile(token, rowId, fieldName, file, context_id);
      onChange(uploaded); // inform parent/grid of new value
      notify({ message: t("fileUploaded"), type: "success" });
    } catch (err) {
      notify({ message: err?.message || t("fileUploadFailed"), type: "error" });
    }
    setUploading(false);
  };

  return (
    <Box display="flex" alignItems="center" gap={1}>
      {value
        ? (
          <>
            <Link href={value.url || value} target="_blank" rel="noopener">
              <AttachFile fontSize="small" />
            </Link>
            {!disabled && (
              <Tooltip title={t("deleteFile")}>
                <IconButton size="small" onClick={() => onChange(null)} aria-label={t("deleteFile")}>
                  <Delete fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </>
        )
        : (
          !disabled && (
            <>
              <input
                type="file"
                style={{ display: "none" }}
                ref={fileInputRef}
                onChange={handleUpload}
                accept=".pdf,image/*"
              />
              <Tooltip title={rowId ? t("uploadFile") : t("saveRowFirstHint")}>
                <span>
                  <IconButton
                    size="small"
                    onClick={() => {
                      if (!rowId) {
                        notify({ message: t("saveRowFirst"), type: "error" });
                        return;
                      }
                      fileInputRef.current?.click();
                    }}
                    disabled={uploading || !rowId}
                    aria-label={t("uploadFile")}
                  >
                    {uploading ? <CircularProgress size={20} /> : <CloudUpload fontSize="small" />}
                  </IconButton>
                </span>
              </Tooltip>
            </>
          )
        )
      }
    </Box>
  );
}