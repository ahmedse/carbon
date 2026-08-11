// src/pages/NotFound.jsx
// 404 page for unknown routes — enterprise recovery surface.
// "Never a dead end" — every error offers a next step.

import React, { useState, useMemo } from "react";
import {
  Box, Typography, Button, TextField, InputAdornment,
  List, ListItemButton, ListItemText, Chip, Stack, Paper,
} from "@mui/material";
import { Link, useLocation } from "react-router-dom";
import SearchIcon from "@mui/icons-material/Search";
import DashboardIcon from "@mui/icons-material/Dashboard";
import DatasetIcon from "@mui/icons-material/Dataset";
import CategoryIcon from "@mui/icons-material/Category";
import SettingsIcon from "@mui/icons-material/Settings";
import BugReportIcon from "@mui/icons-material/BugReport";
import useDocumentTitle from "../hooks/useDocumentTitle";

/** Known platform paths for client-side search. */
const KNOWN_PATHS = [
  { label: "Dashboard", path: "/carbon/dashboard", keywords: "dashboard emissions overview" },
  { label: "My Data", path: "/carbon/my-data", keywords: "my data entry tables modules" },
  { label: "Console", path: "/carbon/console", keywords: "console analytics summary" },
  { label: "Catalog", path: "/catalog", keywords: "catalog products assets metadata" },
  { label: "Calculations", path: "/carbon/calculations", keywords: "calculations audit" },
  { label: "Verification", path: "/carbon/verification", keywords: "verification review" },
  { label: "Settings", path: "/settings", keywords: "settings preferences" },
  { label: "Help", path: "/help", keywords: "help documentation support" },
  { label: "Admin — Users", path: "/admin/users", keywords: "admin users management" },
  { label: "Admin — Org Units", path: "/admin/org-units", keywords: "admin org units organization" },
  { label: "Admin — Access Control", path: "/admin/access", keywords: "admin access control roles" },
  { label: "Admin — Audit Log", path: "/admin/audit", keywords: "admin audit log" },
  { label: "Reporting", path: "/carbon/reporting/generate", keywords: "reporting reports generate" },
  { label: "DQ Workspace", path: "/dq", keywords: "data quality dq workspace rules jobs" },
  { label: "Emission Factors", path: "/carbon/admin/factors", keywords: "emission factors admin" },
];

const SUGGESTED = [
  { label: "Dashboard", path: "/carbon/dashboard", icon: DashboardIcon },
  { label: "My Data", path: "/carbon/my-data", icon: DatasetIcon },
  { label: "Catalog", path: "/catalog", icon: CategoryIcon },
  { label: "Settings", path: "/settings", icon: SettingsIcon },
];

/**
 * 404 Not Found page — recovery surface with search + suggested pages.
 */
export default function NotFound() {
  useDocumentTitle("Page Not Found");
  const location = useLocation();
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return KNOWN_PATHS.filter(
      (p) => p.label.toLowerCase().includes(q) || p.keywords.includes(q)
    ).slice(0, 6);
  }, [query]);

  return (
    <Box
      sx={{
        minHeight: "60vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        px: 2,
      }}
    >
      <Typography variant="h2" color="primary" gutterBottom>
        404
      </Typography>
      <Typography variant="h5" color="text.secondary" gutterBottom>
        Page Not Found
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mb: 3, maxWidth: 480, textAlign: "center" }}
      >
        The page{" "}
        <Box
          component="code"
          sx={{
            bgcolor: "action.hover",
            px: 0.5,
            borderRadius: 0.5,
            fontSize: "0.8rem",
          }}
        >
          {location.pathname}
        </Box>{" "}
        doesn't exist. Try searching or pick from the most-used pages below.
      </Typography>

      {/* Search */}
      <TextField
        placeholder="Search for a page…"
        size="small"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        sx={{ width: 340, maxWidth: "90vw", mb: 2 }}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" color="action" />
              </InputAdornment>
            ),
          },
        }}
      />

      {/* Search results */}
      {results.length > 0 && (
        <Paper
          variant="outlined"
          sx={{ width: 340, maxWidth: "90vw", mb: 3, maxHeight: 240, overflow: "auto" }}
        >
          <List dense disablePadding>
            {results.map((r) => (
              <ListItemButton key={r.path} component={Link} to={r.path}>
                <ListItemText
                  primary={r.label}
                  secondary={r.path}
                  primaryTypographyProps={{ variant: "body2", fontWeight: 500 }}
                  secondaryTypographyProps={{
                    variant: "caption",
                    sx: { fontFamily: "monospace" },
                  }}
                />
                <Chip label="Go" size="small" variant="outlined" sx={{ ml: 1 }} />
              </ListItemButton>
            ))}
          </List>
        </Paper>
      )}

      {/* Suggested pages */}
      <Typography variant="overline" color="text.secondary" sx={{ mb: 1 }}>
        Suggested pages
      </Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap" justifyContent="center" sx={{ mb: 2 }}>
        {SUGGESTED.map((s) => {
          const Icon = s.icon;
          return (
            <Button
              key={s.path}
              variant="outlined"
              size="small"
              component={Link}
              to={s.path}
              startIcon={<Icon fontSize="small" />}
            >
              {s.label}
            </Button>
          );
        })}
      </Stack>

      {/* Report */}
      <Button
        variant="text"
        size="small"
        component={Link}
        to={`/feedback?source=404&path=${encodeURIComponent(location.pathname)}`}
        startIcon={<BugReportIcon fontSize="small" />}
        sx={{ mt: 1 }}
      >
        Report this issue
      </Button>
    </Box>
  );
}