// File: src/shell/Breadcrumbs.jsx
// Breadcrumb navigation showing current location in app hierarchy

import React from 'react';
import { Box, Breadcrumbs as MuiBreadcrumbs, Typography, Link } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import HomeIcon from '@mui/icons-material/Home';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DashboardIcon from '@mui/icons-material/Dashboard';
import Co2Icon from '@mui/icons-material/Co2';
import StorageIcon from '@mui/icons-material/Storage';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import SettingsIcon from '@mui/icons-material/Settings';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import AssignmentIcon from '@mui/icons-material/Assignment';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import AssessmentIcon from '@mui/icons-material/Assessment';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import SecurityIcon from '@mui/icons-material/Security';
import LayersIcon from '@mui/icons-material/Layers';
import LabelIcon from '@mui/icons-material/Label';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DownloadIcon from '@mui/icons-material/Download';
import EditIcon from '@mui/icons-material/Edit';

// Breadcrumb configuration based on routes
const ROUTE_CONFIG = {
  '/dashboard': {
    label: 'Dashboard',
    icon: DashboardIcon,
    parent: null,
  },
  '/dashboard/analytics': {
    label: 'Analytics',
    icon: DashboardIcon,
    parent: '/dashboard',
  },
  '/dashboard/reports': {
    label: 'Reports',
    icon: DashboardIcon,
    parent: '/dashboard',
  },
  '/emissions': {
    label: 'Emissions',
    icon: Co2Icon,
    parent: null,
  },
  '/emissions/add': {
    label: 'Add Activity',
    icon: Co2Icon,
    parent: '/emissions',
  },
  '/emissions/categories': {
    label: 'Categories',
    icon: Co2Icon,
    parent: '/emissions',
  },
  '/emissions/factors': {
    label: 'Emission Factors',
    icon: Co2Icon,
    parent: '/emissions',
  },
  '/dataschema': {
    label: 'Data Hub',
    icon: StorageIcon,
    parent: null,
  },
  '/schema-admin': {
    label: 'Schema Admin',
    icon: StorageIcon,
    parent: '/dataschema',
  },
  '/admin': {
    label: 'Admin',
    icon: AdminPanelSettingsIcon,
    parent: null,
  },
  '/admin/users': {
    label: 'Users',
    icon: AdminPanelSettingsIcon,
    parent: '/admin',
  },
  '/admin/organizations': {
    label: 'Organizations',
    icon: AdminPanelSettingsIcon,
    parent: '/admin',
  },
  '/admin/roles': {
    label: 'Roles',
    icon: AdminPanelSettingsIcon,
    parent: '/admin',
  },
  '/settings': {
    label: 'Settings',
    icon: SettingsIcon,
    parent: null,
  },
  '/help': {
    label: 'Help',
    icon: HelpOutlineIcon,
    parent: null,
  },
  '/feedback': {
    label: 'Feedback',
    icon: HelpOutlineIcon,
    parent: '/help',
  },
  '/catalog': {
    label: 'Catalog Studio',
    icon: DashboardIcon,
    parent: null,
  },
  '/catalog/schemas': {
    label: 'Schema Catalog',
    icon: StorageIcon,
    parent: '/catalog',
  },
  '/catalog/schemas/:tableId': {
    label: 'Schema Detail',
    icon: StorageIcon,
    parent: '/catalog/schemas',
  },
  '/catalog/schema-manager': {
    label: 'Schema Manager',
    icon: AssignmentIcon,
    parent: '/catalog',
  },
  '/catalog/schema-manager/:tableId': {
    label: 'Schema Details',
    icon: AssignmentIcon,
    parent: '/catalog/schema-manager',
  },
  '/catalog/domains': {
    label: 'Domains',
    icon: LocationOnIcon,
    parent: '/catalog',
  },
  '/catalog/glossary': {
    label: 'Glossary',
    icon: AssessmentIcon,
    parent: '/catalog',
  },
  '/catalog/assets': {
    label: 'Assets',
    icon: AssignmentIcon,
    parent: '/catalog',
  },
  '/catalog/tags': {
    label: 'Tags',
    icon: LabelIcon,
    parent: '/catalog',
  },
  '/catalog/reference-data': {
    label: 'Reference Data',
    icon: LayersIcon,
    parent: '/catalog',
  },
  '/catalog/mdm': {
    label: 'MDM',
    icon: AccountTreeIcon,
    parent: '/catalog',
  },
  '/catalog/connections': {
    label: 'Connections',
    icon: SecurityIcon,
    parent: '/catalog',
  },
  '/catalog/importexport': {
    label: 'Import / Export',
    icon: CloudUploadIcon,
    parent: '/catalog',
  },
  '/catalog/sources': {
    label: 'Data Sources',
    icon: StorageIcon,
    parent: '/catalog',
  },
  '/catalog/exports': {
    label: 'Exports',
    icon: DownloadIcon,
    parent: '/catalog',
  },
  '/catalog/imports': {
    label: 'Imports',
    icon: CloudUploadIcon,
    parent: '/catalog',
  },
  '/catalog/governance': {
    label: 'Governance',
    icon: VerifiedUserIcon,
    parent: '/catalog',
  },
};

function normalizePath(pathname) {
  return pathname.replace(/\/+$|^\/+/, '').replace(/\/+/g, '/');
}

function matchRouteConfig(pathname) {
  const cleanPath = normalizePath(pathname);
  const normalizedWithSlash = cleanPath.startsWith('/') ? cleanPath : `/${cleanPath}`;
  if (ROUTE_CONFIG[normalizedWithSlash]) {
    return { config: ROUTE_CONFIG[normalizedWithSlash], path: normalizedWithSlash };
  }

  const segments = cleanPath.split('/').filter(Boolean);
  for (const [routePath, config] of Object.entries(ROUTE_CONFIG)) {
    const routeSegments = normalizePath(routePath).split('/').filter(Boolean);
    if (routeSegments.length !== segments.length) continue;

    const isMatch = routeSegments.every((segment, index) => {
      if (segment.startsWith(':')) return true;
      return segment === segments[index];
    });

    if (isMatch) {
      return { config, path: `/${segments.join('/')}` };
    }
  }

  return null;
}

/**
 * Build breadcrumb trail from current path
 */
function buildBreadcrumbs(pathname) {
  const trail = [];
  let current = normalizePath(pathname);

  // Add home as first item
  trail.unshift({
    path: '/dashboard',
    label: 'Home',
    icon: HomeIcon,
  });

  while (current && current !== 'dashboard' && current !== '/dashboard') {
    const match = matchRouteConfig(current.startsWith('/') ? current : `/${current}`);
    if (!match || !match.config) {
      const parentPath = current.includes('/')
        ? current.substring(0, current.lastIndexOf('/'))
        : '/dashboard';
      current = parentPath || '/dashboard';
      continue;
    }

    trail.push({
      path: current.startsWith('/') ? current : `/${current}`,
      label: match.config.label,
      icon: match.config.icon,
    });

    current = match.config.parent || (current.includes('/') ? current.substring(0, current.lastIndexOf('/')) : '/dashboard');
    if (!current) current = '/dashboard';
  }

  return trail;
}

export function Breadcrumbs() {
  const location = useLocation();
  const navigate = useNavigate();

  const breadcrumbs = buildBreadcrumbs(location.pathname);

  if (breadcrumbs.length <= 1) {
    // Don't show breadcrumbs on home page
    return null;
  }

  return (
    <Box
      component="nav"
      aria-label="Breadcrumb navigation"
      sx={{
        height: 32,
        display: 'flex',
        alignItems: 'center',
        px: 2,
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <MuiBreadcrumbs
        separator={<ChevronRightIcon sx={{ fontSize: 14, color: 'text.disabled' }} />}
        aria-label="breadcrumb"
        sx={{ fontSize: '0.8125rem' }}
      >
        {breadcrumbs.map((crumb, index) => {
          const Icon = crumb.icon;
          const isLast = index === breadcrumbs.length - 1;

          if (isLast) {
            // Current page - not clickable
            return (
              <Box
                key={crumb.path}
                aria-current="page"
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  color: 'text.primary',
                }}
              >
                <Icon sx={{ fontSize: 16 }} aria-hidden="true" />
                <Typography
                  sx={{
                    fontSize: '0.8125rem',
                    fontWeight: 600,
                    color: 'text.primary',
                  }}
                >
                  {crumb.label}
                </Typography>
              </Box>
            );
          }

          // Parent pages - clickable
          return (
            <Link
              key={crumb.path}
              component="button"
              onClick={() => navigate(crumb.path)}
              aria-label={`Navigate to ${crumb.label}`}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                cursor: 'pointer',
                textDecoration: 'none',
                color: 'text.secondary',
                background: 'none',
                border: 'none',
                padding: 0,
                '&:hover': {
                  color: 'primary.main',
                  textDecoration: 'underline',
                },
                '&:focus-visible': {
                  outline: '2px solid',
                  outlineColor: 'primary.main',
                  outlineOffset: '2px',
                  borderRadius: 0.5,
                },
              }}
            >
              <Icon sx={{ fontSize: 16 }} aria-hidden="true" />
              <Typography sx={{ fontSize: '0.8125rem' }}>{crumb.label}</Typography>
            </Link>
          );
        })}
      </MuiBreadcrumbs>
    </Box>
  );
}
