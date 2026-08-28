// src/pages/NotFound.jsx
// 404 page for unknown routes — enterprise recovery surface.
// "Never a dead end" — every error offers a next step.

import React, { useState, useMemo } from "react";
import {
  Box, Typography, Button, TextField, InputAdornment,
  List, ListItemButton, ListItemText, Chip, Stack, Paper,
} from "@mui/material";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import SearchIcon from "@mui/icons-material/Search";
import DashboardIcon from "@mui/icons-material/Dashboard";
import DatasetIcon from "@mui/icons-material/Dataset";
import CategoryIcon from "@mui/icons-material/Category";
import SettingsIcon from "@mui/icons-material/Settings";
import BugReportIcon from "@mui/icons-material/BugReport";
import useDocumentTitle from "../hooks/useDocumentTitle";

/** Known platform paths for client-side search. */
const KNOWN_PATHS = [
  { labelKey: "npDashboard", path: "/carbon/dashboard", keywords: "dashboard emissions overview" },
  { labelKey: "npMyData", path: "/carbon/my-data", keywords: "my data entry tables modules" },
  { labelKey: "npConsole", path: "/carbon/console", keywords: "console analytics summary" },
  { labelKey: "npCatalog", path: "/catalog", keywords: "catalog products assets metadata" },
  { labelKey: "npCalculations", path: "/carbon/calculations", keywords: "calculations audit" },
  { labelKey: "npVerification", path: "/carbon/verification", keywords: "verification review" },
  { labelKey: "npSettings", path: "/settings", keywords: "settings preferences" },
  { labelKey: "npHelp", path: "/help", keywords: "help documentation support" },
  { labelKey: "npAdminUsers", path: "/admin/users", keywords: "admin users management" },
  { labelKey: "npAdminOrgUnits", path: "/admin/org-units", keywords: "admin org units organization" },
  { labelKey: "npAdminAccess", path: "/admin/access", keywords: "admin access control roles" },
  { labelKey: "npAdminAudit", path: "/admin/audit", keywords: "admin audit log" },
  { labelKey: "npReports", path: "/carbon/reporting", keywords: "reporting reports generate saved" },
  { labelKey: "npDqWorkspace", path: "/dq", keywords: "data quality dq workspace rules jobs" },
  { labelKey: "npEmissionFactors", path: "/carbon/admin/factors", keywords: "emission factors admin" },
];

const SUGGESTED = [
  { labelKey: "npDashboard", path: "/carbon/dashboard", icon: DashboardIcon },
  { labelKey: "npMyData", path: "/carbon/my-data", icon: DatasetIcon },
  { labelKey: "npCatalog", path: "/catalog", icon: CategoryIcon },
  { labelKey: "npSettings", path: "/settings", icon: SettingsIcon },
];

/**
 * 404 Not Found page — recovery surface with search + suggested pages.
 */
export default function NotFound() {
  const { t } = useTranslation('common');
  useDocumentTitle(t("pageNotFound"));
  const location = useLocation();
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return KNOWN_PATHS.filter(
      (p) => t(p.labelKey).toLowerCase().includes(q) || p.keywords.includes(q)
    ).slice(0, 6);
  }, [query, t]);

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
        {t("pageNotFound")}
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mb: 3, maxWidth: 480, textAlign: "center" }}
      >
        {t("notFoundSentence1")}{" "}
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
        {t("notFoundSentence2")}
      </Typography>

      {/* Search */}
      <TextField
        placeholder={t("searchForPage")}
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
                  primary={t(r.labelKey)}
                  secondary={r.path}
                  primaryTypographyProps={{ variant: "body2", fontWeight: 500 }}
                  secondaryTypographyProps={{
                    variant: "caption",
                    sx: { fontFamily: "monospace" },
                  }}
                />
                <Chip label={t("go")} size="small" variant="outlined" sx={{ ml: 1 }} />
              </ListItemButton>
            ))}
          </List>
        </Paper>
      )}

      {/* Suggested pages */}
      <Typography variant="overline" color="text.secondary" sx={{ mb: 1 }}>
        {t("suggestedPages")}
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
              {t(s.labelKey)}
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