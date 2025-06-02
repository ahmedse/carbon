// File: src/components/FileCellRenderer.jsx

import React, { useRef, useState } from "react";
import { Box, IconButton, Link, CircularProgress, Tooltip } from "@mui/material";
import { AttachFile, Delete, CloudUpload } from "@mui/icons-material";
import { useNotification } from "./NotificationProvider";

export default function FileCellRenderer({
  value, onChange, disabled, rowId, fieldName, uploadRowFile, token, context_id
}) {
  const fileInputRef = useRef();
  const [uploading, setUploading] = useState(false);
  const notify = useNotification();

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!rowId) {
      notify({ message: "Please save the row before uploading a file.", type: "error" });
      return;
    }
    setUploading(true);
    try {
      const uploaded = await uploadRowFile(token, rowId, fieldName, file, context_id);
      onChange(uploaded); // inform parent/grid of new value
      notify({ message: "File uploaded.", type: "success" });
    } catch (err) {
      notify({ message: err?.message || "File upload failed", type: "error" });
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
              <Tooltip title="Delete file">
                <IconButton size="small" onClick={() => onChange(null)} aria-label="Delete file">
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
              <Tooltip title={rowId ? "Upload file" : "Save row first"}>
                <span>
                  <IconButton
                    size="small"
                    onClick={() => {
                      if (!rowId) {
                        notify({ message: "Please save the row before uploading a file.", type: "error" });
                        return;
                      }
                      fileInputRef.current?.click();
                    }}
                    disabled={uploading || !rowId}
                    aria-label="Upload file"
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