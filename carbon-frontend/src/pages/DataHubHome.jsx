import React, { useEffect } from "react";
import { Box, Typography, Card, CardContent, Grid, Button, Chip } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import StorageIcon from '@mui/icons-material/Storage';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';

const SCOPE_COLORS = {
  1: { bg: '#e8f5e9', color: '#2e7d32', label: 'Scope 1' },
  2: { bg: '#e3f2fd', color: '#1565c0', label: 'Scope 2' },
  3: { bg: '#fff3e0', color: '#e65100', label: 'Scope 3' },
};

export default function DataHubHome() {
  const navigate = useNavigate();
  const { context, availablePerspectives, tablesByModule } = useAuth();
  const modules = context?.modules || [];
  const isAdmin = availablePerspectives?.includes('admin');

  useEffect(() => {
    if (modules.length === 1 && !isAdmin) {
      navigate(`/modules/${modules[0].id}`, { replace: true });
    }
  }, [modules, isAdmin, navigate]);

  if (modules.length === 1 && !isAdmin) {
    return (
      <Box p={3} textAlign="center">
        <Typography variant="h5">Loading your module...</Typography>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3} flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Data Hub
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Select a module to enter or manage data.
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
        <Grid container spacing={2}>
          {modules.map((module) => {
            const scope = module.scope || 1;
            const scopeStyle = SCOPE_COLORS[scope] || SCOPE_COLORS[1];
            const tableCount = (tablesByModule?.[String(module.id)] || []).length;

            return (
              <Grid item xs={12} sm={6} md={4} key={module.id}>
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
                      <StorageIcon color="primary" />
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
    </Box>
  );
}
