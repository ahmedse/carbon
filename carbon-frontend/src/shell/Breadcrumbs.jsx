// File: src/shell/Breadcrumbs.jsx
// Breadcrumb navigation showing current location in app hierarchy

import React from 'react';
import { Box, Breadcrumbs as MuiBreadcrumbs, Typography, Link } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
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
    label: 'Carbon Data Entry',
    icon: StorageIcon,
    parent: null,
  },
  '/carbon/console': {
    label: 'Carbon Console',
    icon: Co2Icon,
    parent: null,
  },
  '/carbon/dashboard': {
    label: 'Emissions Dashboard',
    icon: DashboardIcon,
    parent: '/carbon/console',
  },
  '/carbon/owner/portal': {
    label: 'Data Owner Portal',
    icon: LocationOnIcon,
    parent: '/carbon/console',
  },
  '/carbon/owner/dashboard': {
    label: 'My Dashboard',
    icon: DashboardIcon,
    parent: '/carbon/owner/portal',
  },
  '/carbon/owner/assets': {
    label: 'My Emission Sources',
    icon: StorageIcon,
    parent: '/carbon/owner/portal',
  },
  '/carbon/reporting/generate': {
    label: 'Generate Report',
    icon: AssessmentIcon,
    parent: '/carbon/console',
  },
  '/carbon/reporting/saved': {
    label: 'Saved Reports',
    icon: AssessmentIcon,
    parent: '/carbon/console',
  },
  '/carbon/reporting/periods': {
    label: 'Reporting Periods',
    icon: AssignmentIcon,
    parent: '/carbon/console',
  },
  '/carbon/admin/factors': {
    label: 'Emission Factors',
    icon: Co2Icon,
    parent: '/carbon/console',
  },
  '/carbon/my-data': {
    label: 'My Data',
    icon: StorageIcon,
    parent: '/carbon/console',
  },
  '/carbon/my-data/:moduleId': {
    label: 'Source Workspace',
    icon: StorageIcon,
    parent: '/carbon/my-data',
  },
  '/carbon/my-data/:moduleId/:tableId': {
    label: 'Data Entry',
    icon: StorageIcon,
    parent: '/carbon/my-data/:moduleId',
  },
  '/carbon/data-entry': {
    label: 'Activity Data Entry',
    icon: StorageIcon,
    parent: '/carbon/my-data',
  },
  '/carbon/data-entry/entry/:moduleId/:tableId': {
    label: 'Data Entry',
    icon: StorageIcon,
    parent: '/carbon/data-entry',
  },
  '/carbon/data-entry/row/:tableId/:rowId': {
    label: 'Row Detail',
    icon: StorageIcon,
    parent: '/carbon/data-entry',
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
  '/catalog/products': {
    label: 'Data Products',
    icon: StorageIcon,
    parent: '/catalog',
  },
  '/catalog/products/:moduleId': {
    label: 'Data Product',
    icon: StorageIcon,
    parent: '/catalog/products',
  },
  '/catalog/tables/:tableId': {
    label: 'Table',
    icon: StorageIcon,
    parent: '/catalog/products',
  },
  '/catalog/schemas': {
    label: 'Data Products',
    icon: StorageIcon,
    parent: '/catalog',
  },
  '/catalog/schemas/:tableId': {
    label: 'Table',
    icon: StorageIcon,
    parent: '/catalog/products',
  },
  '/catalog/metadata': {
    label: 'Metadata Management',
    icon: LocationOnIcon,
    parent: '/catalog',
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

function fillPathParams(parentPath, currentPath) {
  const parentSegments = normalizePath(parentPath).split('/').filter(Boolean);
  const currentSegments = normalizePath(currentPath).split('/').filter(Boolean);

  return `/${parentSegments.map((segment, index) => (
    segment.startsWith(':') ? currentSegments[index] || segment : segment
  )).join('/')}`;
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
  const chain = [];
  let current = normalizePath(pathname);

  // Walk UP from the current page to the root, collecting each crumb.
  while (current && current !== 'dashboard' && current !== '/dashboard') {
    const match = matchRouteConfig(current.startsWith('/') ? current : `/${current}`);
    if (!match || !match.config) {
      const parentPath = current.includes('/')
        ? current.substring(0, current.lastIndexOf('/'))
        : '/dashboard';
      current = parentPath || '/dashboard';
      continue;
    }

    chain.push({
      path: current.startsWith('/') ? current : `/${current}`,
      label: match.config.label,
      icon: match.config.icon,
    });

    current = match.config.parent || (current.includes('/') ? current.substring(0, current.lastIndexOf('/')) : '/dashboard');
    if (current && current.includes(':')) {
      current = fillPathParams(current, match.path);
    }
    if (!current) current = '/dashboard';
  }

  // chain is [current, parent, grandparent, …] — reverse to root→current order,
  // then prepend Home so the trail reads Home → … → current.
  chain.reverse();

  return [
    { path: '/dashboard', label: 'Home', icon: HomeIcon },
    ...chain,
  ];
}

/**
 * Smart label resolution: replace generic labels on dynamic entity routes with
 * the REAL entity name (e.g. "Facilities - Electricity", "Monthly Electricity").
 * Resolved client-side from AuthContext (modules + tablesByModule) — no fetch.
 */
function resolveCrumbLabel(crumb, modules, tablesByModule) {
  const segs = crumb.path.split('/').filter(Boolean);
  const last = segs[segs.length - 1];

  // Data Product / module detail: /catalog/products/:id or /modules/:id
  if ((segs[0] === 'catalog' && segs[1] === 'products' && segs[2]) ||
      (segs[0] === 'modules' && segs[1])) {
    const mod = (modules || []).find((m) => String(m.id) === String(last));
    if (mod?.name) return mod.name;
  }

  // Data entry routes: /carbon/my-data/:moduleId and /carbon/my-data/:moduleId/:tableId
  if (segs[0] === 'carbon' && segs[1] === 'my-data' && segs[2] && segs.length === 3) {
    const mod = (modules || []).find((m) => String(m.id) === String(segs[2]));
    if (mod?.name) return mod.name;
  }

  if (segs[0] === 'carbon' && segs[1] === 'my-data' && segs[2] && segs[3]) {
    const moduleId = segs[2];
    const tableId = segs[3];
    const tables = tablesByModule?.[String(moduleId)] || [];
    const table = tables.find((x) => String(x.id) === String(tableId));
    if (table?.title || table?.name) return table.title || table.name;
  }

  // Table detail: /catalog/tables/:id or /catalog/schemas/:id (legacy)
  if (segs[0] === 'catalog' && (segs[1] === 'tables' || segs[1] === 'schemas') && segs[2]) {
    for (const arr of Object.values(tablesByModule || {})) {
      const t = (arr || []).find((x) => String(x.id) === String(last));
      if (t) return t.title || t.name || crumb.label;
    }
  }

  return crumb.label;
}

export function Breadcrumbs() {
  const location = useLocation();
  const navigate = useNavigate();
  const { context, tablesByModule } = useAuth();
  const modules = context?.modules || [];

  const breadcrumbs = buildBreadcrumbs(location.pathname).map((crumb) => ({
    ...crumb,
    label: resolveCrumbLabel(crumb, modules, tablesByModule),
  }));

  if (breadcrumbs.length <= 1) {
    // Don't show breadcrumbs on home page
    return null;
  }

  return (
    <Box
      component="nav"
      aria-label="Breadcrumb navigation"
      sx={{
        height: 30,
        display: 'flex',
        alignItems: 'center',
        px: 2,
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.default',
      }}
    >
      <MuiBreadcrumbs
        separator={<ChevronRightIcon sx={{ fontSize: 11, color: 'text.disabled' }} />}
        aria-label="breadcrumb"
        sx={{ fontSize: '0.65rem' }}
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
                <Icon sx={{ fontSize: 14 }} aria-hidden="true" />
                <Typography
                  sx={{
                    fontSize: '0.75rem',
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
              <Icon sx={{ fontSize: 14 }} aria-hidden="true" />
              <Typography sx={{ fontSize: '0.75rem' }}>{crumb.label}</Typography>
            </Link>
          );
        })}
      </MuiBreadcrumbs>
    </Box>
  );
}
