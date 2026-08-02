import React, { useEffect, useState, useMemo } from "react";
import { Box, Typography, Card, CardContent, Grid, Button, Chip, Tabs, Tab } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import StorageIcon from '@mui/icons-material/Storage';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import { NatureRounded, BoltRounded, LocalShippingRounded } from "@mui/icons-material";
import useDocumentTitle from '../hooks/useDocumentTitle';

const SCOPE_COLORS = {
  1: { bg: '#e8f5e9', color: '#2e7d32', label: 'Scope 1' },
  2: { bg: '#e3f2fd', color: '#1565c0', label: 'Scope 2' },
  3: { bg: '#fff3e0', color: '#e65100', label: 'Scope 3' },
};

const SCOPE_ICONS = {
  1: <NatureRounded sx={{ fontSize: 16, color: '#2e7d32' }} />,
  2: <BoltRounded sx={{ fontSize: 16, color: '#1565c0' }} />,
  3: <LocalShippingRounded sx={{ fontSize: 16, color: '#e65100' }} />,
};

export default function DataHubHome() {
  useDocumentTitle("Data Hub");
  const navigate = useNavigate();
  const { context, availablePerspectives, tablesByModule } = useAuth();
  const modules = context?.modules || [];
  const isAdmin = availablePerspectives?.includes('admin');

  const [scopeFilter, setScopeFilter] = useState('all');

  useEffect(() => {
    if (modules.length === 1 && !isAdmin) {
      navigate(`/modules/${modules[0].id}`, { replace: true });
    }
  }, [modules, isAdmin, navigate]);

  // Count modules per scope for tab labels
  const scopeCounts = useMemo(() => {
    const counts = { 1: 0, 2: 0, 3: 0 };
    modules.forEach(m => {
      const s = m.scope || 1;
      if (counts[s] !== undefined) counts[s]++;
    });
    return counts;
  }, [modules]);

  // Filter modules by selected scope
  const filteredModules = useMemo(() => {
    if (scopeFilter === 'all') return modules;
    return modules.filter(m => String(m.scope || 1) === scopeFilter);
  }, [modules, scopeFilter]);

  if (modules.length === 1 && !isAdmin) {
    return (
      <Box p={3} textAlign="center">
        <Typography variant="h5">Loading your module...</Typography>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2} flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Carbon Data Entry Hub
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Select a module to enter or manage your carbon emissions data.
          </Typography>
        </Box>

        {isAdmin && (
          <Button
            variant="contained"
            startIcon={<AdminPanelSettingsIcon />}
            onClick={() => navigate('/schema-admin/table-manager')}
          >
            Manage All Tables
          </Button>
        )}
      </Box>

      {modules.length === 0 ? (
        <Box textAlign="center" py={8}>
          <StorageIcon sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No Data Modules Assigned
          </Typography>
          <Typography variant="body2" color="text.secondary" mt={1}>
            Contact your administrator to get access to data entry modules.
          </Typography>
        </Box>
      ) : (
        <>
          {/* Scope filter tabs */}
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
            <Tabs
              value={scopeFilter}
              onChange={(_, val) => setScopeFilter(val)}
              sx={{
                minHeight: 40,
                '& .MuiTab-root': {
                  minHeight: 40,
                  py: 0.75,
                  textTransform: 'none',
                  fontWeight: 500,
                  fontSize: '0.8125rem',
                },
              }}
            >
              <Tab value="all" label={`All Modules (${modules.length})`} />
              {scopeCounts[1] > 0 && (
                <Tab
                  value="1"
                  label={
                    <Box display="flex" alignItems="center" gap={0.5}>
                      {SCOPE_ICONS[1]}
                      {`Scope 1 (${scopeCounts[1]})`}
                    </Box>
                  }
                />
              )}
              {scopeCounts[2] > 0 && (
                <Tab
                  value="2"
                  label={
                    <Box display="flex" alignItems="center" gap={0.5}>
                      {SCOPE_ICONS[2]}
                      {`Scope 2 (${scopeCounts[2]})`}
                    </Box>
                  }
                />
              )}
              {scopeCounts[3] > 0 && (
                <Tab
                  value="3"
                  label={
                    <Box display="flex" alignItems="center" gap={0.5}>
                      {SCOPE_ICONS[3]}
                      {`Scope 3 (${scopeCounts[3]})`}
                    </Box>
                  }
                />
              )}
            </Tabs>
          </Box>

          {filteredModules.length === 0 ? (
            <Box textAlign="center" py={6}>
              <Typography color="text.secondary">No modules for this scope.</Typography>
            </Box>
          ) : (
            <Grid container spacing={2}>
              {filteredModules.map((module) => {
                const scope = module.scope || 1;
                const scopeStyle = SCOPE_COLORS[scope] || SCOPE_COLORS[1];
                const tableCount = (tablesByModule?.[String(module.id)] || []).length;

                return (
                  <Grid size={{ xs: 12, sm: 6, md: 4 }} key={module.id}>
                    <Card
                      variant="outlined"
                      sx={{
                        cursor: 'pointer',
                        height: '100%',
                        transition: 'all 0.2s',
                        '&:hover': {
                          boxShadow: 3,
                          borderColor: 'primary.main',
                          transform: 'translateY(-2px)',
                        },
                      }}
                      onClick={() => navigate(`/modules/${module.id}`)}
                    >
                      <CardContent>
                        <Box display="flex" alignItems="center" gap={1} mb={2}>
                          {SCOPE_ICONS[scope]}
                          <Typography variant="h6" fontWeight={600}>
                            {module.name}
                          </Typography>
                        </Box>
                        <Typography variant="body2" color="text.secondary" mb={2} minHeight={40}>
                          {module.description || 'No description'}
                        </Typography>
                        <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
                          <Chip
                            label={scopeStyle.label}
                            size="small"
                            sx={{
                              bgcolor: scopeStyle.bg,
                              color: scopeStyle.color,
                              fontWeight: 600,
                            }}
                          />
                          <Chip
                            label={`${tableCount} ${tableCount === 1 ? 'table' : 'tables'}`}
                            size="small"
                          />
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          )}
        </>
      )}
    </Box>
  );
}
