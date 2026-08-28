// src/pages/ScopeInfoPage.jsx

import React from "react";
import { useTranslation } from "react-i18next";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Divider,
  Card,
  CardContent,
  Grid,
  Chip,
  TextField,
  InputAdornment
} from "@mui/material";
import useDocumentTitle from '../hooks/useDocumentTitle';

import {
  NatureRounded as Scope1Icon,
  BoltRounded as Scope2Icon,
  LocalShippingRounded as Scope3Icon,
} from "@mui/icons-material";
import SearchIcon from "@mui/icons-material/Search";
import { useAuth } from "../auth/AuthContext";

export default function ScopeInfoPage() {
  const { t } = useTranslation("emissions");
  useDocumentTitle(t("scopeDetailTitle"));

  const SCOPE_DETAILS = React.useMemo(() => ({
    1: {
      label: t("scope1Label"),
      icon: <Scope1Icon sx={{ fontSize: '2.5rem', color: "success.main", verticalAlign: "middle" }} />,
      description: t("scope1Detail"),
      examples: t("scope1Examples", { returnObjects: true }),
    },
    2: {
      label: t("scope2Label"),
      icon: <Scope2Icon sx={{ fontSize: '2.5rem', color: "primary.main", verticalAlign: "middle" }} />,
      description: t("scope2Detail"),
      examples: t("scope2Examples", { returnObjects: true }),
    },
    3: {
      label: t("scope3Label"),
      icon: <Scope3Icon sx={{ fontSize: '2.5rem', color: "warning.main", verticalAlign: "middle" }} />,
      description: t("scope3Detail"),
      examples: t("scope3Examples", { returnObjects: true }),
    },
  }), [t]);

  const { scopeId } = useParams();
  const scope = SCOPE_DETAILS[scopeId];
  const { context, tablesByModule } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = React.useState("");

  // Only modules for this scope
  const modules = React.useMemo(() => {
    return (context?.modules || []).filter(m =>
      String(m.scope) === String(scopeId) &&
      (!search ||
        m.name.toLowerCase().includes(search.toLowerCase()) ||
        m.description?.toLowerCase().includes(search.toLowerCase()))
    );
  }, [context, scopeId, search]);

  // Helper to get stats per module
  function getModuleStats(mod) {
    const tables = tablesByModule?.[mod.id] || [];
    const totalRows = tables.reduce((sum, t) => sum + (t.row_count ?? 0), 0);
    return { tablesCount: tables.length, totalRows };
  }

  if (!scope) return <Typography>{t("scopeNotFound")}</Typography>;

  return (
    <Box
      sx={{
        width: "100%",
        minHeight: "100vh",
        px: { xs: 1, sm: 3, md: 5 },
        py: { xs: 2, md: 4 },
        bgcolor: "background.dark"
      }}
    >
      <Typography
        variant="h4"
        fontWeight={700}
        mb={1}
        display="flex"
        alignItems="center"
        gap={1}
        sx={{ px: { xs: 0, sm: 1 } }}
      >
        {scope.icon} {scope.label}
      </Typography>
      <Divider sx={{ my: 2 }} />
      <Typography
        variant="body1"
        mb={2}
        sx={{ color: "text.secondary", fontSize: "1.1rem", px: { xs: 0, sm: 1 } }}
      >
        {scope.description}
      </Typography>
      <Typography
        variant="subtitle1"
        fontWeight={600}
        mb={1}
        sx={{ px: { xs: 0, sm: 1 } }}
      >
        {t("realWorldExamples")}:
      </Typography>
      <ul style={{ marginLeft: 24 }}>
        {scope.examples.map((ex, i) => (
          <li key={i} style={{ color: "#555", marginBottom: 6 }}>{ex}</li>
        ))}
      </ul>

      <Box mt={6} mb={2}>
        <Typography variant="h5" mb={2} fontWeight={700}>
          {t("modulesInScope")}
        </Typography>
        <TextField
          placeholder={t("filterModules")}
          value={search}
          onChange={e => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ mb: 3, width: 320 }}
          size="small"
        />
      </Box>
      <Grid container spacing={3}>
        {modules.length === 0 && (
          <Grid size={{ xs: 12 }}>
            <Typography color="text.secondary">{t("noModulesForScope")}</Typography>
          </Grid>
        )}
        {modules.map(mod => {
          const stats = getModuleStats(mod);
          return (
            <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={mod.id}>
              <Card
                variant="outlined"
                sx={{
                  cursor: "pointer",
                  ":hover": { boxShadow: 4, borderColor: "primary.light" },
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  minHeight: 170,
                  transition: "box-shadow 0.2s",
                  bgcolor: "background.default",
                }}
                onClick={() => navigate(`/modules/${mod.id}`)}
              >
                <CardContent>
                  <Box display="flex" alignItems="center" gap={1} mb={1}>
                    {scope.icon}
                    <Typography fontWeight={600} fontSize={18}>
                      {mod.name}
                    </Typography>
                  </Box>
                  <Typography color="text.secondary" fontSize={13} mb={1}>
                    {mod.description}
                  </Typography>
                  <Box mt={1} display="flex" alignItems="center" gap={1} flexWrap="wrap">
                    <Chip size="small" label={t("tablesCount", { count: stats.tablesCount })} />
                    <Chip size="small" label={t("rowsCount", { count: stats.totalRows })} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}