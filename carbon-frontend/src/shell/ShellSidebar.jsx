// File: src/shell/ShellSidebar.jsx
// Studio-specific sidebar navigation content with perspective awareness

import React, { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { Box, List, ListItemButton, ListItemIcon, ListItemText, Typography, IconButton, Tooltip, Divider } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DashboardIcon from '@mui/icons-material/Dashboard';
import BarChartIcon from '@mui/icons-material/BarChart';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TableChartIcon from '@mui/icons-material/TableChart';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import RuleIcon from '@mui/icons-material/Rule';
import HistoryIcon from '@mui/icons-material/History';
import PeopleIcon from '@mui/icons-material/People';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import SecurityIcon from '@mui/icons-material/Security';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import EditIcon from '@mui/icons-material/Edit';
import StorageIcon from '@mui/icons-material/Storage';
import DownloadIcon from '@mui/icons-material/Download';
import UploadIcon from '@mui/icons-material/Upload';
import AssignmentIcon from '@mui/icons-material/Assignment';
import LayersIcon from '@mui/icons-material/Layers';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import ScienceIcon from '@mui/icons-material/Science';
import FolderIcon from '@mui/icons-material/Folder';
import GroupIcon from '@mui/icons-material/Group';
import AppsIcon from '@mui/icons-material/Apps';
import GridViewIcon from '@mui/icons-material/GridView';
import { useAuth } from '../auth/AuthContext';
import { APP_REGISTRY } from '../apps/registry';

// UI-driven icon mapping for Carbon sidebar items
// This allows icons to be chosen at runtime without hardcoding
const CARBON_ITEM_ICONS = {
  'My Portal':         LocationOnIcon,
  'My Dashboard':      BarChartIcon,
  'My Assets':         StorageIcon,
  'Carbon Data Entry': AddCircleOutlineIcon,
  'Generate Report':   AssessmentIcon,
  'Saved Reports':   FolderIcon,
  'Analytics':       BarChartIcon,
  'Emission Factors': ScienceIcon,
  'Reporting Periods': AssignmentIcon,
  'Table Manager':   TableChartIcon,
  'Dashboard':       DashboardIcon,
};

// Define sidebar content per studio
function getSidebarItems(studioId) {
  switch (studioId) {
    case 'home':
      return [
        { label: 'Executive Summary', path: '/dashboards/executive', icon: DashboardIcon },
        { label: 'Analytics', path: '/dashboards/analytics', icon: BarChartIcon },
        { label: 'Targets', path: '/dashboards/targets', icon: AssessmentIcon },
      ];
    
    case 'carbon': {
      // Carbon app — read from manifest, resolve icons by label (same pattern as Catalog)
      const carbonApp = APP_REGISTRY.find(m => m.id === 'carbon');
      if (carbonApp && carbonApp.navigation && carbonApp.navigation.items) {
        return carbonApp.navigation.items.map(item => ({
          ...item,
          icon: CARBON_ITEM_ICONS[item.label] || DashboardIcon,
        }));
      }
      return [];
    }
    
    case 'catalog':
      return [
        { label: 'Catalog Home', path: '/catalog', icon: DashboardIcon },
        { type: 'divider' },
        { type: 'group', label: 'Data Products' },
        { label: 'Data Products', path: '/catalog/products', icon: TableChartIcon },
        { type: 'divider' },
        { type: 'group', label: 'Governance' },
        { label: 'Metadata', path: '/catalog/metadata', icon: EditIcon },
        { label: 'Asset Profiles', path: '/catalog/assets', icon: AssignmentIcon },
        { label: 'DQ Dashboard', path: '/catalog/dq-dashboard', icon: RuleIcon },
        { label: 'DQ Rules', path: '/catalog/dq-rules', icon: HistoryIcon },
        { label: 'Governance Policies', path: '/catalog/policies', icon: RuleIcon },
        { label: 'Governance Audit', path: '/catalog/governance', icon: VerifiedUserIcon },
        { type: 'divider' },
        { type: 'group', label: 'Master Data' },
        { label: 'Reference Sets', path: '/catalog/reference-data', icon: LayersIcon },
        { label: 'Master Data', path: '/catalog/mdm', icon: AccountTreeIcon },
        { type: 'divider' },
        { type: 'group', label: 'Data Integration' },
        { label: 'Connections', path: '/catalog/connections', icon: SecurityIcon },
        { label: 'Data Sources', path: '/catalog/sources', icon: StorageIcon },
        { label: 'Exports', path: '/catalog/exports', icon: DownloadIcon },
        { label: 'Imports', path: '/catalog/imports', icon: UploadIcon },
      ];
    
    case 'admin':
      return [
        { label: 'Users', path: '/admin/users', icon: PeopleIcon, role: 'admin' },
        { label: 'Groups & Roles', path: '/admin/groups', icon: GroupIcon, role: 'admin' },
        { label: 'Org Units', path: '/admin/org-units', icon: AccountTreeIcon, role: 'admin' },
        { label: 'Access Control', path: '/admin/access', icon: SecurityIcon, role: 'admin' },
        { label: 'Audit Log', path: '/admin/audit', icon: HistoryIcon, role: 'admin' },
        { type: 'divider' },
        { type: 'group', label: 'App Management' },
        { label: 'Registered Apps', path: '/admin/apps', icon: AppsIcon, role: 'admin' },
        { label: 'Role Registry', path: '/admin/role-matrix', icon: GridViewIcon, role: 'admin' },
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
    
    default: {
      // Dynamic lookup: if this studioId is a manifest app, return its nav items.
      // This makes ALL future apps work with zero additional changes here.
      const manifest = APP_REGISTRY.find(m => m.id === studioId);
      if (manifest) {
        return manifest.navigation.items.map(item => ({
          ...item,
          icon: DashboardIcon,   // Future: add iconName to manifest nav items for dynamic resolution
        }));
      }
      return [];
    }
   }
}

function getStudioTitle(studioId) {
  const titles = {
    home:    'Dashboard',
    catalog: 'Catalog Studio',
    admin:   'Platform Admin',
    settings:'Settings',
    help:    'Help & Support',
  };
  return titles[studioId]
    || APP_REGISTRY.find(m => m.id === studioId)?.name
    || 'Carbon';
}

export function ShellSidebar({ activeStudio, onNavigate, onCollapse }) {
  const { currentPerspective, availablePerspectives, context } = useAuth();
  const location = useLocation();

  // Filter items based on perspective and available admin status
  let items = getSidebarItems(activeStudio);
  const title = getStudioTitle(activeStudio);
  
  // If in admin studio, filter based on whether user has admin perspective
  const canAccessPlatformAdmin = availablePerspectives.includes('admin') || availablePerspectives.includes('platform-admin');
  if (activeStudio === 'admin' && !canAccessPlatformAdmin) {
    items = []; // Hide all admin items for non-admin users
  }
  
  // Filter items by role-based access (for Carbon and other manifest-driven apps)
  if (activeStudio === 'carbon') {
    const userRoles = availablePerspectives || [];
    items = items.filter(item => {
      // Always show items without role restriction (role: '*') or no role set
      if (!item.role || item.role === '*') return true;
      // Show dividers and groups always
      if (item.type === 'divider' || item.type === 'group') return true;
      // For regular items with role: check if user has that role
      // Match both full role format (carbon:data_owner) and short format (data-owner)
      if (item.role.includes(':')) {
        // Extract the role suffix after ':' and convert underscore to hyphen
        const roleSuffix = item.role.split(':')[1].replace(/_/g, '-');
        return userRoles.includes(roleSuffix) || userRoles.includes('admin');
      }
      return userRoles.includes(item.role);
    });
  }

  // Compute org unit and scope summary for carbon context header
  const { userOrgUnit, moduleSummary } = useMemo(() => {
    if (activeStudio !== 'carbon') return {};
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

  const normalizedLocation = location.pathname.replace(/\/+$|^\/+/, '');

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

      {/* Context header — only in Carbon studio */}
      {activeStudio === 'carbon' && (userOrgUnit || moduleSummary) && (
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
          (() => {
            const rendered = [];
            let lastWasDivider = false;
            
            items.forEach((item, index) => {
              // Skip rendering if no type or path for the item
              if (!item.type && !item.path) {
                return;
              }

              // Handle divider
              if (item.type === 'divider') {
                // Skip consecutive dividers
                if (!lastWasDivider && rendered.length > 0) {
                  rendered.push(
                    <Divider key={`divider-${index}`} sx={{ my: 0.5 }} />
                  );
                  lastWasDivider = true;
                }
                return;
              }

              // Handle group header
              if (item.type === 'group') {
                rendered.push(
                  <Typography
                    key={`group-${item.label}`}
                    variant="caption"
                    sx={{
                      px: 1.5,
                      py: 1,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      fontSize: '0.7rem',
                      color: 'text.secondary',
                      letterSpacing: '0.05em',
                      display: 'block',
                      mt: 1,
                    }}
                  >
                    {item.label}
                  </Typography>
                );
                lastWasDivider = false;
                return;
              }

              // Handle regular navigation items
              const Icon = item.icon;
              const itemPath = item.path ? item.path.replace(/\/+$|^\/+/, '') : '';
              const isActive = itemPath && (normalizedLocation === itemPath || normalizedLocation.startsWith(`${itemPath}/`));
              rendered.push(
                <ListItemButton
                  key={item.path}
                  onClick={() => onNavigate(item)}
                  selected={isActive}
                  sx={{
                    borderRadius: 1,
                    mb: 0.5,
                    py: 1,
                    px: 1.5,
                    bgcolor: isActive ? 'action.selected' : 'transparent',
                    '&:hover': {
                      bgcolor: 'action.hover',
                    },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>
                    <Icon sx={{ fontSize: 18, color: isActive ? 'primary.main' : 'text.secondary' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{
                      fontSize: '0.8125rem',
                      fontWeight: isActive ? 700 : 500,
                      color: isActive ? 'text.primary' : 'text.secondary',
                    }}
                  />
                </ListItemButton>
              );
              lastWasDivider = false;
            });
            
            return rendered;
          })()
        )}
      </List>
    </Box>
  );
}
