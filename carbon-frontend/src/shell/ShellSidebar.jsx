// File: src/shell/ShellSidebar.jsx
// Studio-specific sidebar navigation content with perspective awareness

import React, { useMemo } from 'react';
import { Box, List, ListItemButton, ListItemIcon, ListItemText, Typography, IconButton, Tooltip, Divider } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DashboardIcon from '@mui/icons-material/Dashboard';
import BarChartIcon from '@mui/icons-material/BarChart';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TableChartIcon from '@mui/icons-material/TableChart';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import RuleIcon from '@mui/icons-material/Rule';
import PeopleIcon from '@mui/icons-material/People';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import SecurityIcon from '@mui/icons-material/Security';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { useAuth } from '../auth/AuthContext';

// Define sidebar content per studio
function getSidebarItems(studioId) {
  switch (studioId) {
    case 'home':
      return [
        { label: 'Executive Summary', path: '/dashboards/executive', icon: DashboardIcon },
        { label: 'Analytics', path: '/dashboards/analytics', icon: BarChartIcon },
        { label: 'Targets', path: '/dashboards/targets', icon: AssessmentIcon },
      ];
    
    case 'emissions':
      return [
        { label: 'Dashboard', path: '/emissions/dashboard', icon: DashboardIcon },
        { label: 'Report', path: '/emissions/report', icon: AssessmentIcon },
      ];
    
    case 'dataschema':
      return [
        { label: 'Data Entry', path: '/dataschema', icon: AddCircleOutlineIcon },
        { label: 'Table Manager', path: '/schema-admin/table-manager', icon: TableChartIcon },
        { label: 'Data Quality', path: '/dataschema/quality', icon: RuleIcon },
      ];
    
    case 'admin':
      return [
        { label: 'Users', path: '/admin/users', icon: PeopleIcon },
        { label: 'Org Units', path: '/admin/org-units', icon: AccountTreeIcon },
        { label: 'Access Control', path: '/admin/access', icon: SecurityIcon },
      ];
    
    case 'settings':
      return [
        { label: 'Profile', path: '/settings/profile', icon: PeopleIcon },
        { label: 'Preferences', path: '/settings/preferences', icon: RuleIcon },
      ];
    
    case 'help':
      return [
        { label: 'Documentation', path: '/help', icon: DashboardIcon },
        { label: 'Feedback', path: '/feedback', icon: AssessmentIcon },
      ];
    
    default:
      return [];
  }
}

function getStudioTitle(studioId) {
  const titles = {
    home: 'Dashboard',
    emissions: 'Emissions',
    dataschema: 'Data Hub',
    admin: 'Administration',
    settings: 'Settings',
    help: 'Help & Support',
  };
  return titles[studioId] || 'Carbon';
}

export function ShellSidebar({ activeStudio, onNavigate, onCollapse }) {
  const { currentPerspective, availablePerspectives, context } = useAuth();
  
  // Filter items based on perspective and available admin status
  let items = getSidebarItems(activeStudio);
  const title = getStudioTitle(activeStudio);
  
  // If in admin studio, filter based on whether user has admin perspective
  if (activeStudio === 'admin' && !availablePerspectives.includes('admin')) {
    items = []; // Hide all admin items for non-admin users
  }
  
  // If in dataschema studio, hide Table Manager for non-admins
  if (activeStudio === 'dataschema' && !availablePerspectives.includes('admin')) {
    items = items.filter(item => item.path !== '/schema-admin/table-manager');
  }

  // Compute org unit and scope summary for dataschema context header
  const { userOrgUnit, moduleSummary } = useMemo(() => {
    if (activeStudio !== 'dataschema') return {};
    const modules = context?.modules || [];
    const orgName = modules.find(m => m.org_unit_name)?.org_unit_name || null;

    // Build scope breakdown: { 1: n, 2: n, 3: n }
    const scopeCount = {};
    modules.forEach(m => {
      const s = m.scope || 1;
      scopeCount[s] = (scopeCount[s] || 0) + 1;
    });

    const parts = [];
    if (scopeCount[1]) parts.push(`${scopeCount[1]}×S1`);
    if (scopeCount[2]) parts.push(`${scopeCount[2]}×S2`);
    if (scopeCount[3]) parts.push(`${scopeCount[3]}×S3`);

    const summary = modules.length > 0
      ? `${modules.length} module${modules.length !== 1 ? 's' : ''}${parts.length ? `: ${parts.join(', ')}` : ''}`
      : null;

    return { userOrgUnit: orgName, moduleSummary: summary };
  }, [activeStudio, context]);

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.paper',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1.5,
          borderBottom: '1px solid',
          borderColor: 'divider',
          flexShrink: 0,
        }}
      >
        <Typography
          sx={{
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: 'text.primary',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          {title}
        </Typography>
        <Tooltip title="Hide Sidebar (Ctrl+B)" placement="right">
          <IconButton
            size="small"
            onClick={onCollapse}
            sx={{
              width: 24,
              height: 24,
              color: 'text.secondary',
              '&:hover': { color: 'text.primary', bgcolor: 'action.hover' },
            }}
          >
            <ChevronLeftIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Context header — only in Data Hub */}
      {activeStudio === 'dataschema' && (userOrgUnit || moduleSummary) && (
        <Box
          sx={{
            px: 2,
            py: 1,
            borderBottom: '1px solid',
            borderColor: 'divider',
            flexShrink: 0,
            bgcolor: (t) =>
              t.palette.mode === 'light' ? 'rgba(14,165,233,0.04)' : 'rgba(56,189,248,0.06)',
          }}
        >
          {userOrgUnit && (
            <Box display="flex" alignItems="center" gap={0.5} mb={0.25}>
              <LocationOnIcon sx={{ fontSize: 12, color: 'primary.main' }} aria-hidden="true" />
              <Typography
                variant="caption"
                sx={{
                  color: 'text.primary',
                  fontWeight: 500,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: 160,
                }}
                title={userOrgUnit}
              >
                {userOrgUnit}
              </Typography>
            </Box>
          )}
          {moduleSummary && (
            <Typography
              variant="caption"
              sx={{ color: 'text.secondary', display: 'block', fontSize: '0.6875rem' }}
            >
              {moduleSummary}
            </Typography>
          )}
        </Box>
      )}

      {/* Navigation items */}
      <List
        sx={{
          flex: 1,
          overflow: 'auto',
          py: 1,
          px: 1,
        }}
      >
        {items.length === 0 ? (
          <Box sx={{ px: 2, py: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              No items available
            </Typography>
          </Box>
        ) : (
          items.map((item) => {
            const Icon = item.icon;
            return (
              <ListItemButton
                key={item.path}
                onClick={() => onNavigate(item)}
                sx={{
                  borderRadius: 1,
                  mb: 0.5,
                  py: 1,
                  px: 1.5,
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <Icon sx={{ fontSize: 18, color: 'text.secondary' }} />
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    fontSize: '0.8125rem',
                    fontWeight: 500,
                  }}
                />
              </ListItemButton>
            );
          })
        )}
      </List>
    </Box>
  );
}
