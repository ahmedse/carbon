import React, { useState, useEffect, useCallback } from "react";
import {
  Box, Paper, Typography, TextField, Select, MenuItem, FormControl,
  InputLabel, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Chip, IconButton, Tooltip, CircularProgress, Alert,
  Switch, FormControlLabel, Pagination, Collapse,
} from "@mui/material";
import {
  Refresh as RefreshIcon,
  ContentCopy as CopyIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
} from "@mui/icons-material";
import useDocumentTitle from "../../hooks/useDocumentTitle";
import { apiFetch } from "../../api/api";

const LEVEL_COLORS = {
  DEBUG: "default",
  INFO: "primary",
  WARNING: "warning",
  ERROR: "error",
  CRITICAL: "error",
};

const LEVELS = ["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

export default function LogViewerPage() {
  useDocumentTitle("System Logs");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [entries, setEntries] = useState([]);
  const [totalMatched, setTotalMatched] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [fileInfo, setFileInfo] = useState({ file_size_bytes: 0, total_lines_in_file: 0 });
  const [logFiles, setLogFiles] = useState([]);

  // Filters
  const [level, setLevel] = useState("");
  const [search, setSearch] = useState("");
  const [correlationId, setCorrelationId] = useState("");
  const [selectedFile, setSelectedFile] = useState("carbon.log");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Expanded row for detail view
  const [expandedRow, setExpandedRow] = useState(null);

  const fetchLogFiles = useCallback(async () => {
    try {
      const data = await apiFetch("/system/logs/?list=1");
      setLogFiles(data.files || []);
    } catch {
      // Non-critical — user can still type a filename
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("log_file", selectedFile);
      params.set("lines", "500");
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      if (level) params.set("level", level);
      if (search) params.set("search", search);
      if (correlationId) params.set("correlation_id", correlationId);

      const data = await apiFetch(`/system/logs/?${params.toString()}`);
      setEntries(data.entries || []);
      setTotalMatched(data.total_matched || 0);
      setTotalPages(data.total_pages || 0);
      setFileInfo({
        file_size_bytes: data.file_size_bytes || 0,
        total_lines_in_file: data.total_lines_in_file || 0,
      });
    } catch (err) {
      setError(err.message || "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, [selectedFile, level, search, correlationId, page, pageSize]);

  useEffect(() => {
    fetchLogFiles();
  }, [fetchLogFiles]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchLogs, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchLogs]);

  const copyCorrelationId = (id) => {
    navigator.clipboard.writeText(id).catch(() => {});
  };

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatTimestamp = (ts) => {
    if (!ts) return "";
    // asctime format: "2026-08-09 17:46:48,244"
    const [date, time] = ts.split(" ");
    return `${date} ${(time || "").split(",")[0]}`;
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3 }}>
        <Typography variant="h5" fontWeight={600}>
          System Logs
        </Typography>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                size="small"
              />
            }
            label="Auto-refresh (30s)"
          />
          <Tooltip title="Refresh">
            <IconButton onClick={fetchLogs} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* File info bar */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        File: <strong>{selectedFile}</strong> — {fileInfo.total_lines_in_file.toLocaleString()} lines,{" "}
        {formatBytes(fileInfo.file_size_bytes)} — Showing {totalMatched} matching entries
      </Typography>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 2, display: "flex", gap: 2, flexWrap: "wrap", alignItems: "center" }}>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Log File</InputLabel>
          <Select
            value={selectedFile}
            label="Log File"
            onChange={(e) => { setSelectedFile(e.target.value); setPage(1); }}
          >
            {logFiles.length > 0 ? (
              logFiles.map((f) => (
                <MenuItem key={f.name} value={f.name}>
                  {f.name} ({formatBytes(f.size_bytes)})
                </MenuItem>
              ))
            ) : (
              <MenuItem value="carbon.log">carbon.log</MenuItem>
            )}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Level</InputLabel>
          <Select
            value={level}
            label="Level"
            onChange={(e) => { setLevel(e.target.value); setPage(1); }}
          >
            {LEVELS.map((l) => (
              <MenuItem key={l} value={l}>
                {l || "ALL"}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField
          size="small"
          label="Search"
          placeholder="Search logs..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          sx={{ flex: 1, minWidth: 200 }}
        />

        <TextField
          size="small"
          label="Correlation ID"
          placeholder="Filter by correlation ID"
          value={correlationId}
          onChange={(e) => { setCorrelationId(e.target.value); setPage(1); }}
          sx={{ minWidth: 220 }}
        />
      </Paper>

      {/* Error */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>
          {error}
        </Alert>
      )}

      {/* Table */}
      <TableContainer component={Paper} sx={{ maxHeight: "calc(100vh - 320px)" }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 160, fontWeight: 600 }}>Timestamp</TableCell>
              <TableCell sx={{ width: 80, fontWeight: 600 }}>Level</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Message</TableCell>
              <TableCell sx={{ width: 140, fontWeight: 600 }}>Logger</TableCell>
              <TableCell sx={{ width: 40 }} />
            </TableRow>
          </TableHead>
          <TableBody>
            {loading && entries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 6 }}>
                  <CircularProgress size={32} />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Loading logs…
                  </Typography>
                </TableCell>
              </TableRow>
            ) : entries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 6 }}>
                  <Typography variant="body2" color="text.secondary">
                    No log entries match the current filters.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              entries.map((entry, idx) => (
                <React.Fragment key={idx}>
                  <TableRow
                    hover
                    sx={{ cursor: "pointer" }}
                    onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}
                  >
                    <TableCell sx={{ whiteSpace: "nowrap", fontFamily: "monospace", fontSize: "0.8rem" }}>
                      {formatTimestamp(entry.asctime)}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={entry.levelname}
                        size="small"
                        color={LEVEL_COLORS[entry.levelname] || "default"}
                        variant="filled"
                        sx={{ fontWeight: 600, fontSize: "0.7rem" }}
                      />
                    </TableCell>
                    <TableCell sx={{ maxWidth: 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {entry.message}
                    </TableCell>
                    <TableCell sx={{ fontFamily: "monospace", fontSize: "0.75rem", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {entry.name}
                    </TableCell>
                    <TableCell>
                      {expandedRow === idx ? <CollapseIcon /> : <ExpandIcon />}
                    </TableCell>
                  </TableRow>
                  {/* Expanded detail row */}
                  <TableRow>
                    <TableCell colSpan={5} sx={{ p: 0, borderBottom: expandedRow === idx ? undefined : "none" }}>
                      <Collapse in={expandedRow === idx}>
                        <Box sx={{ p: 2, bgcolor: "#f8fafc" }}>
                          <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap", mb: 1 }}>
                            <Box>
                              <Typography variant="caption" color="text.secondary">Path</Typography>
                              <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                                {entry.pathname}:{entry.lineno}
                              </Typography>
                            </Box>
                            {entry.method && (
                              <Box>
                                <Typography variant="caption" color="text.secondary">Method</Typography>
                                <Typography variant="body2">{entry.method}</Typography>
                              </Box>
                            )}
                            {entry.status_code && (
                              <Box>
                                <Typography variant="caption" color="text.secondary">Status</Typography>
                                <Chip
                                  label={entry.status_code}
                                  size="small"
                                  color={entry.status_code >= 400 ? "error" : entry.status_code >= 300 ? "warning" : "success"}
                                />
                              </Box>
                            )}
                            {entry.duration_ms != null && (
                              <Box>
                                <Typography variant="caption" color="text.secondary">Duration</Typography>
                                <Typography variant="body2">{entry.duration_ms} ms</Typography>
                              </Box>
                            )}
                            {entry.user && (
                              <Box>
                                <Typography variant="caption" color="text.secondary">User</Typography>
                                <Typography variant="body2">{entry.user}</Typography>
                              </Box>
                            )}
                            {entry.remote_addr && (
                              <Box>
                                <Typography variant="caption" color="text.secondary">IP</Typography>
                                <Typography variant="body2">{entry.remote_addr}</Typography>
                              </Box>
                            )}
                          </Box>
                          {entry.correlation_id && (
                            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                              <Typography variant="caption" color="text.secondary">Correlation ID:</Typography>
                              <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                                {entry.correlation_id}
                              </Typography>
                              <Tooltip title="Copy correlation ID">
                                <IconButton size="small" onClick={() => copyCorrelationId(entry.correlation_id)}>
                                  <CopyIcon fontSize="inherit" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          )}
                          <Box sx={{ mt: 1 }}>
                            <Typography variant="caption" color="text.secondary">Raw JSON</Typography>
                            <pre style={{
                              fontSize: "0.7rem", fontFamily: "monospace",
                              background: "#fff", padding: 8, borderRadius: 4,
                              border: "1px solid #e2e8f0", overflow: "auto", maxHeight: 200,
                            }}>
                              {JSON.stringify(entry, null, 2)}
                            </pre>
                          </Box>
                        </Box>
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </React.Fragment>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(_, p) => setPage(p)}
            color="primary"
            showFirstButton
            showLastButton
          />
        </Box>
      )}
    </Box>
  );
}
