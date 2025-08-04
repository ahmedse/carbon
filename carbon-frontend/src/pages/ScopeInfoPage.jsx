// src/pages/ScopeInfoPage.jsx

import React from "react";
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
import {
  NatureRounded as Scope1Icon,
  BoltRounded as Scope2Icon,
  LocalShippingRounded as Scope3Icon,
} from "@mui/icons-material";
import SearchIcon from "@mui/icons-material/Search";
import { useAuth } from "../auth/AuthContext";

const SCOPE_DETAILS = {
  1: {
    label: "Scope 1: Direct Emissions",
    icon: <Scope1Icon sx={{ fontSize: 40, color: "#43a047", verticalAlign: "middle" }} />,
    description: "Direct greenhouse gas (GHG) emissions from sources owned or controlled by your organization, such as company vehicles, on-site fuel combustion, or manufacturing activities.",
    examples: [
      "Company-owned vehicles",
      "Stationary combustion (boilers, furnaces)",
      "Process emissions from chemical production"
    ]
  },
  2: {
    label: "Scope 2: Indirect Energy Emissions",
    icon: <Scope2Icon sx={{ fontSize: 40, color: "#1e88e5", verticalAlign: "middle" }} />,
    description: "Indirect GHG emissions from the generation of purchased electricity, steam, heating, and cooling consumed by your organization.",
    examples: [
      "Purchased electricity for offices and factories",
      "Purchased steam or heating/cooling utilities"
    ]
  },
  3: {
    label: "Scope 3: Value Chain Emissions",
    icon: <Scope3Icon sx={{ fontSize: 40, color: "#ff7043", verticalAlign: "middle" }} />,
    description: "Other indirect GHG emissions that occur in the value chain of your organization, both upstream and downstream (including suppliers and product use by customers).",
    examples: [
      "Business travel and employee commuting",
      "Waste disposal",
      "Use of sold products",
      "Transportation and distribution",
      "Purchased goods and services"
    ]
  },
};

export default function ScopeInfoPage() {
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

  if (!scope) return <Typography>Scope not found.</Typography>;

  return (
    <Box
      sx={{
        width: "100%",
        minHeight: "100vh",
        px: { xs: 1, sm: 3, md: 5 },
        py: { xs: 2, md: 4 },
        bgcolor: "#f5f7fa"
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
        sx={{ color: "#444", fontSize: "1.1rem", px: { xs: 0, sm: 1 } }}
      >
        {scope.description}
      </Typography>
      <Typography
        variant="subtitle1"
        fontWeight={600}
        mb={1}
        sx={{ px: { xs: 0, sm: 1 } }}
      >
        Real-world examples:
      </Typography>
      <ul style={{ marginLeft: 24 }}>
        {scope.examples.map((ex, i) => (
          <li key={i} style={{ color: "#555", marginBottom: 6 }}>{ex}</li>
        ))}
      </ul>

      <Box mt={6} mb={2}>
        <Typography variant="h5" mb={2} fontWeight={700}>
          Modules in this Scope
        </Typography>
        <TextField
          placeholder="Filter modules..."
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
          <Grid item xs={12}>
            <Typography color="text.secondary">No modules found for this scope.</Typography>
          </Grid>
        )}
        {modules.map(mod => {
          const stats = getModuleStats(mod);
          return (
            <Grid item xs={12} sm={6} md={4} lg={3} key={mod.id}>
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
                  bgcolor: "#fff",
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
                    <Chip size="small" label={`Tables: ${stats.tablesCount}`} />
                    <Chip size="small" label={`Rows: ${stats.totalRows}`} />
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