// File: src/pages/PlatformHome.jsx
// Platform Home — single entry page showing accessible domain apps as cards.
// Replaces the old ExecutiveSummary/Analytics/Targets dashboard trio.
// RULE: Never add emissions-specific dashboards here; they live inside domain apps.

import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  CardActionArea,
  Typography,
  Grid,
  Avatar,
  Chip,
} from '@mui/material';
import Co2Icon from '@mui/icons-material/Co2';
import DashboardIcon from '@mui/icons-material/Dashboard';
import LayersIcon from '@mui/icons-material/Layers';
import { APP_REGISTRY } from '../apps/registry';
import { useAuth } from '../auth/AuthContext';
import { hasAppAccess } from '../utils/rbac';
import { useEnabledApps } from '../hooks/useEnabledApps';
import useDocumentTitle from '../hooks/useDocumentTitle';

// Icon lookup — maps manifest icon names to MUI icon components.
// Move 3: replace with a full MUI dynamic icon loader for runtime resolution.
const APP_ICONS = {
  Co2: Co2Icon,
  Dashboard: DashboardIcon,
  Layers: LayersIcon,
};

function AppCard({ app }) {
  const navigate = useNavigate();
  const Icon = APP_ICONS[app.icon] || DashboardIcon;

  const handleClick = () => {
    navigate(app.routePrefix || `/${app.id}`);
  };

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderTop: `4px solid ${app.color || '#2563eb'}`,
        transition: 'box-shadow 0.2s, transform 0.15s',
        '&:hover': {
          boxShadow: 6,
          transform: 'translateY(-3px)',
        },
      }}
    >
      <CardActionArea onClick={handleClick} sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}>
        <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
            <Avatar
              sx={{
                bgcolor: app.color || 'primary.main',
                width: 40,
                height: 40,
              }}
            >
              <Icon />
            </Avatar>
            <Typography variant="h6" fontWeight={600} noWrap>
              {app.name}
            </Typography>
          </Box>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ flex: 1, mb: 1.5 }}
          >
            {app.description}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {(app.roles || []).slice(0, 3).map((role) => (
              <Chip
                key={role.key}
                label={role.label}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.6875rem', height: 20 }}
              />
            ))}
            {(app.roles || []).length > 3 && (
              <Chip
                label={`+${app.roles.length - 3}`}
                size="small"
                variant="outlined"
                sx={{ fontSize: '0.6875rem', height: 20 }}
              />
            )}
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

function NoAppsPlaceholder() {
  return (
    <Box sx={{ textAlign: 'center', py: 8 }}>
      <Typography variant="h5" color="text.secondary" gutterBottom>
        No Applications Available
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Contact your administrator to get access to domain applications.
      </Typography>
    </Box>
  );
}

export default function PlatformHome() {
  useDocumentTitle("Platform");
  const { availablePerspectives, user, context, loading } = useAuth();
  const { isAppEnabled } = useEnabledApps();

  // Filter to apps the user can access AND the admin has enabled.
  // Uses centralized hasAppAccess + admin enable/disable from PlatformAppConfig.
  const accessibleApps = APP_REGISTRY.filter((app) => {
    if (loading) return false;
    if (!isAppEnabled(app.id)) return false;
    return hasAppAccess(app.id, user, context, availablePerspectives);
  });

  return (
    <Box
      sx={{
        p: { xs: 2, sm: 3, md: 4 },
        maxWidth: 1100,
        mx: 'auto',
        width: '100%',
      }}
    >
      {/* Platform header */}
      <Box sx={{ mb: 4 }}>
        <Typography
          variant="h4"
          sx={{ fontWeight: 700, color: 'text.primary', mb: 0.5 }}
        >
          Carbon Data Trust Platform
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Trusted data platform hosting domain applications for AASTMT
        </Typography>
      </Box>

      {/* App cards */}
      {accessibleApps.length > 0 ? (
        <Grid container spacing={3}>
          {accessibleApps.map((app) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={app.id}>
              <AppCard app={app} />
            </Grid>
          ))}
        </Grid>
      ) : (
        <NoAppsPlaceholder />
      )}
    </Box>
  );
}
