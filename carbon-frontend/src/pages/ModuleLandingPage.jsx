// src/pages/ModuleLandingPage.jsx
import React, { useMemo, useState } from "react";
import { Box, Typography, Card, CardContent, Grid, InputAdornment, TextField, Chip } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { NatureRounded, BoltRounded, LocalShippingRounded } from "@mui/icons-material";

const scopeIcons = {
  1: <NatureRounded sx={{ color: "#43a047" }} />,
  2: <BoltRounded sx={{ color: "#1e88e5" }} />,
  3: <LocalShippingRounded sx={{ color: "#ff7043" }} />,
};
const scopeLabels = {
  1: "Scope 1",
  2: "Scope 2",
  3: "Scope 3",
};

export default function ModuleLandingPage() {
  const { moduleId } = useParams();
  const navigate = useNavigate();
  const { context, tablesByModule } = useAuth();

  const module = (context?.modules || []).find(m => String(m.id) === String(moduleId));
  const [search, setSearch] = useState("");

  const tables = useMemo(() => {
    return (tablesByModule?.[moduleId] || []).filter(
      t =>
        t.is_active !== false &&
        (t.title?.toLowerCase().includes(search.toLowerCase()) ||
          t.description?.toLowerCase().includes(search.toLowerCase()))
    );
  }, [tablesByModule, moduleId, search]);

  if (!module) {
    return (
      <Box p={4}>
        <Typography color="error" variant="h5">Module not found</Typography>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        {module.name}
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" mb={3}>
        {module.description}
      </Typography>
      <TextField
        placeholder="Search tables..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon />
            </InputAdornment>
          ),
        }}
        sx={{ mb: 3, width: 340 }}
        size="small"
      />
      <Grid container spacing={2}>
        {tables.length === 0 && (
          <Grid item xs={12}>
            <Typography>No tables found.</Typography>
          </Grid>
        )}
        {tables.map(table => (
          <Grid item xs={12} sm={6} md={4} key={table.id}>
            <Card
              variant="outlined"
              sx={{
                cursor: "pointer",
                ":hover": { boxShadow: 3, borderColor: "primary.light" },
                height: "100%",
                display: "flex",
                flexDirection: "column",
              }}
              onClick={() => navigate(`/dataschema/entry/${module.id}/${table.id}`)}
            >
              <CardContent>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  {scopeIcons[table.scope || module.scope] || null}
                  <Typography fontWeight={600} fontSize={18}>
                    {table.title}
                  </Typography>
                </Box>
                <Typography color="text.secondary" fontSize={13} mb={1}>
                  {table.description}
                </Typography>
                <Box mt={1} display="flex" alignItems="center" gap={1} flexWrap="wrap">
                  <Chip
                    size="small"
                    label={scopeLabels[table.scope || module.scope]}
                    color="default"
                    icon={scopeIcons[table.scope || module.scope]}
                  />
                  <Chip
                    size="small"
                    label={`Rows: ${table.row_count ?? 0}`}
                  />
                  <Chip
                    size="small"
                    label={`Created: ${table.created_at ? new Date(table.created_at).toLocaleDateString() : "-"}`}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}