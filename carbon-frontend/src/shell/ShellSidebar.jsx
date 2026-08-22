// File: src/shell/ShellSidebar.jsx
// Studio-specific sidebar navigation content with perspective awareness

import React, { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { Box, List, Typography, IconButton, Tooltip } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import HomeIcon from '@mui/icons-material/Home';
import DashboardIcon from '@mui/icons-material/Dashboard';
import BarChartIcon from '@mui/icons-material/BarChart';
import AssessmentIcon from '@mui/icons-material/Assessment';
import TableChartIcon from '@mui/icons-material/TableChart';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import RuleIcon from '@mui/icons-material/Rule';
import HistoryIcon from '@mui/icons-material/History';
import ArticleIcon from '@mui/icons-material/Article';
import PeopleIcon from '@mui/icons-material/People';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import SecurityIcon from '@mui/icons-material/Security';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import EditIcon from '@mui/icons-material/Edit';
import StorageIcon from '@mui/icons-material/Storage';
import DownloadIcon from '@mui/icons-material/Download';
import UploadIcon from '@mui/icons-material/Upload';
import AssignmentIcon from '@mui/icons-material/Assignment';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import ScienceIcon from '@mui/icons-material/Science';
import FolderIcon from '@mui/icons-material/Folder';
import GroupIcon from '@mui/icons-material/Group';
import AppsIcon from '@mui/icons-material/Apps';
import GridViewIcon from '@mui/icons-material/GridView';
import SettingsIcon from '@mui/icons-material/Settings';
import CalculateIcon from '@mui/icons-material/Calculate';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ChatIcon from '@mui/icons-material/Chat';
import ForumIcon from '@mui/icons-material/Forum';
import PsychologyIcon from '@mui/icons-material/Psychology';
import MemoryIcon from '@mui/icons-material/Memory';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import HubIcon from '@mui/icons-material/Hub';
import HandymanIcon from '@mui/icons-material/Handyman';
import ExtensionIcon from '@mui/icons-material/Extension';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import TuneIcon from '@mui/icons-material/Tune';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import FeedbackIcon from '@mui/icons-material/Feedback';
import LoopIcon from '@mui/icons-material/Loop';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import SchemaIcon from '@mui/icons-material/Schema';
import TimelineIcon from '@mui/icons-material/Timeline';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { useAuth } from '../auth/AuthContext';
import { APP_REGISTRY } from '../apps/registry';
import { can } from '../authz';
import { MENU_ITEM_CAPABILITIES } from '../capabilities';

// UI-driven icon mapping for Carbon sidebar items
// This allows icons to be chosen at runtime without hardcoding
const CARBON_ITEM_ICONS = {
  'Overview':             DashboardIcon,
  'Emissions Dashboard':  BarChartIcon,
  'Analytics & Trends':   BarChartIcon,
  'Data Entry':           AddCircleOutlineIcon,
  'Emission Sources':     StorageIcon,
  'Generate Report':      AssessmentIcon,
  'Saved Reports':        FolderIcon,
  'Reporting Periods':    AssignmentIcon,
  'Emission Factors':     ScienceIcon,
  'Calculation Rules':    ScienceIcon,
  'Calculations':         CalculateIcon,
  'Verification':         VerifiedUserIcon,
  'GWP Reference':        ScienceIcon,
  'SBTi Targets':         TrackChangesIcon,
  'Organizational Boundaries': AccountTreeIcon,
  'Base Years':               HistoryIcon,
  'Table Manager':        TableChartIcon,
  'Dashboard':            DashboardIcon,
};

// Define sidebar content per studio
function getSidebarItems(studioId) {
  switch (studioId) {
    case 'home':
      return [
        { label: 'Platform Home', path: '/', icon: HomeIcon },
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
        { label: 'DQ Workspace', path: '/dq', icon: RuleIcon },
        { label: 'Governance Policies', path: '/catalog/policies', icon: RuleIcon },
        { label: 'Governance Audit', path: '/catalog/governance', icon: VerifiedUserIcon },
        { type: 'divider' },
        { type: 'group', label: 'Master Data' },
        { label: 'Master Data', path: '/catalog/mdm', icon: AccountTreeIcon },
        { type: 'divider' },
        { type: 'group', label: 'Data Integration' },
        { label: 'Connections', path: '/catalog/connections', icon: SecurityIcon },
        { label: 'Data Sources', path: '/catalog/sources', icon: StorageIcon },
        { label: 'Exports', path: '/catalog/exports', icon: DownloadIcon },
        { label: 'Imports', path: '/catalog/imports', icon: UploadIcon },
        { type: 'divider' },
        { type: 'group', label: 'Schema Tools' },
        { label: 'Table Manager', path: '/schema-admin/table-manager', icon: TableChartIcon },
      ];
    
    case 'admin':
      return [
        { label: 'Users', path: '/admin/users', icon: PeopleIcon, role: 'admin' },
        { label: 'Groups & Roles', path: '/admin/groups', icon: GroupIcon, role: 'admin' },
        { label: 'Org Units', path: '/admin/org-units', icon: AccountTreeIcon, role: 'admin' },
        { label: 'Access Control', path: '/admin/access', icon: SecurityIcon, role: 'admin' },
        { label: 'Audit Log', path: '/admin/audit', icon: HistoryIcon, role: 'admin' },
        { label: 'System Logs', path: '/admin/logs', icon: ArticleIcon, role: 'admin' },
        { type: 'divider' },
        { type: 'group', label: 'App Management' },
        { label: 'Registered Apps', path: '/admin/apps', icon: AppsIcon, role: 'admin' },
        { label: 'Role Registry', path: '/admin/role-matrix', icon: GridViewIcon, role: 'admin' },
        { type: 'divider' },
        { type: 'group', label: 'System Settings' },
        { label: 'Platform Config', path: '/admin/config', icon: SettingsIcon, role: 'admin' },
      ];

    case 'ai-admin':
      return [
        { label: 'Overview', path: '/admin/ai', icon: AutoAwesomeIcon, role: 'admin' },
        { label: 'Pulse', path: '/admin/ai/workspace', icon: ChatIcon, role: 'admin' },
        { label: 'Conversations', path: '/admin/ai/conversations', icon: ForumIcon, role: 'admin' },
        { type: 'group', label: 'Intelligence Core' },
        { label: 'Knowledge Base', path: '/admin/ai/knowledge', icon: PsychologyIcon, role: 'admin' },
        { label: 'Memory', path: '/admin/ai/memory', icon: MemoryIcon, role: 'admin' },
        { label: 'Knowledge Graph', path: '/admin/ai/graph', icon: AccountTreeIcon, role: 'admin' },
        { label: 'Budget & Usage', path: '/admin/ai/budget-usage', icon: AccountBalanceWalletIcon, role: 'admin' },
        { label: 'Engine Settings', path: '/admin/ai/engine-settings', icon: TuneIcon, role: 'admin' },
        { type: 'group', label: 'Agents & Tooling' },
        { label: 'Agents', path: '/admin/ai/agents', icon: SmartToyIcon, role: 'admin' },
        { label: 'MCP Servers', path: '/admin/ai/mcp', icon: HubIcon, role: 'admin' },
        { label: 'Tools', path: '/admin/ai/tools', icon: HandymanIcon, role: 'admin' },
        { label: 'Skills Catalog', path: '/admin/ai/skills', icon: ExtensionIcon, role: 'admin' },
        { label: 'Topology', path: '/admin/ai/topology', icon: SchemaIcon, role: 'admin' },
        { label: 'Archetypes', path: '/admin/ai/archetypes', icon: AutoFixHighIcon, role: 'admin' },
        { label: 'Prompts & Playbook', path: '/admin/ai/prompts', icon: MenuBookIcon, role: 'admin' },
        { type: 'group', label: 'Feedback & Learning' },
        { label: 'Feedback Review', path: '/admin/ai/feedback', icon: FeedbackIcon, role: 'admin' },
        { label: 'Learning Jobs', path: '/admin/ai/learning', icon: LoopIcon, role: 'admin' },
        { label: 'Learning Flywheel', path: '/admin/ai/learning-flywheel', icon: AutorenewIcon, role: 'admin' },
        { type: 'group', label: 'Observability' },
        { label: 'Monitoring', path: '/admin/ai/monitoring', icon: MonitorHeartIcon, role: 'admin' },
        { label: 'Output Quality', path: '/admin/ai/output-quality', icon: TrendingDownIcon, role: 'admin' },
        { label: 'Audit Trail', path: '/admin/ai/audit', icon: HistoryIcon, role: 'admin' },
        { label: 'Run Timeline', path: '/admin/ai/runs', icon: TimelineIcon, role: 'admin' },
        { label: 'Logs', path: '/admin/ai/logs', icon: ArticleIcon, role: 'admin' },
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
    
    case 'apps':
      return [
        { label: 'Healthy Dashboard', path: '/apps/healthy', icon: DashboardIcon },
        { type: 'divider' },
        { type: 'group', label: 'Healthy Foods Factory' },
        { label: 'Loadout Sheet', path: '/apps/healthy/loadout', icon: TableChartIcon },
        { label: 'Rep Health', path: '/apps/healthy/reps', icon: PeopleIcon },
        { label: 'AR Queue', path: '/apps/healthy/collections', icon: AccountBalanceWalletIcon },
        { label: 'Slow Movers', path: '/apps/healthy/inventory', icon: StorageIcon },
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
    'ai-admin': 'AI Admin',
    settings:'Settings',
    help:    'Help & Support',
    apps:    'Apps',
  };
  return titles[studioId]
    || APP_REGISTRY.find(m => m.id === studioId)?.name
    || 'Carbon';
}

/**
 * Filter sidebar items by CBAC (capability-based access control).
 * Uses can(user, 'view_menu', label, ctx) for each navigable item.
 * 
 * Items are filtered out if they have a required capability (from MENU_ITEM_CAPABILITIES)
 * and the user lacks it. Items without a mapped capability pass through.
 * Dividers and group headers always pass through.
 *
 * @param {Array} items — sidebar items with {label, path, type?, role?}
 * @param {object} user — current user from AuthContext
 * @param {object} authCtx — {perspectives, isGlobalAdminFlag, capabilities, modules}
 * @returns {Array} filtered items
 */
function filterItemsByCapability(items, user, authCtx) {
  if (!items || !Array.isArray(items)) return [];
  if (!user) return items; // no user yet, show all (loading state)

  return items.filter(item => {
    // Dividers and group headers always pass through
    if (item.type === 'divider' || item.type === 'group') return true;

    // Items with an explicit role marker (legacy admin gating)
    if (item.role && item.role !== '*') {
      // Admin-gated items: check via can() access_route
      if (item.path) {
        return can(user, 'access_route', item.path, authCtx);
      }
    }

    // Items with a label mapped in MENU_ITEM_CAPABILITIES
    if (item.label && MENU_ITEM_CAPABILITIES[item.label]) {
      return can(user, 'view_menu', item.label, authCtx);
    }

    // If item has a path, try route-based check
    if (item.path && item.path !== '/') {
      return can(user, 'access_route', item.path, authCtx);
    }

    // No capability requirement → visible to all authenticated users
    return true;
  });
}

export function ShellSidebar({ activeStudio, onNavigate, onCollapse }) {
  const { currentPerspective: _currentPerspective, availablePerspectives, isGlobalAdminFlag, userCapabilities, context, user } = useAuth();
  const location = useLocation();

  // Build unified auth context for can() calls
  const authCtx = useMemo(() => ({
    perspectives: availablePerspectives,
    isGlobalAdminFlag,
    capabilities: userCapabilities,
    modules: context?.modules || [],
  }), [availablePerspectives, isGlobalAdminFlag, userCapabilities, context]);

  // Filter items based on capability-based access (CBAC)
  let items = getSidebarItems(activeStudio);
  const title = getStudioTitle(activeStudio);

  // If in admin studios, gate with can() — only platform admins see them
  if ((activeStudio === 'admin' || activeStudio === 'ai-admin') && !can(user, 'access_route', '/admin/users', authCtx)) {
    items = []; // Hide all admin items for non-admin users
  }

  // Filter items by CBAC: each menu item gated by can(user, 'view_menu', label, authCtx)
  items = filterItemsByCapability(items, user, authCtx);

  // Prune empty group headers and orphaned dividers after filtering
  items = useMemo(() => {
    if (!items || items.length === 0) return [];
    const pruned = [];
    let i = 0;
    while (i < items.length) {
      const item = items[i];
      if (item.type === 'group') {
        // Look ahead: does this group have any nav items before next group/end?
        let hasContent = false;
        for (let j = i + 1; j < items.length; j++) {
          if (items[j].type === 'group') break; // next group, stop
          if (!items[j].type || items[j].path) { hasContent = true; break; }
        }
        if (hasContent) pruned.push(item);
      } else if (item.type === 'divider') {
        // Keep dividers only when preceded and followed by real content
        const prev = pruned[pruned.length - 1];
        const isPrevContent = prev && (!prev.type || prev.path);
        let isNextContent = false;
        for (let j = i + 1; j < items.length; j++) {
          if (items[j].type === 'divider') continue;
          if (items[j].type === 'group') { isNextContent = false; break; }
          isNextContent = true; break;
        }
        if (isPrevContent && isNextContent) pruned.push(item);
      } else {
        pruned.push(item);
      }
      i++;
    }
    // Strip leading/trailing dividers
    while (pruned.length > 0 && pruned[0].type === 'divider') pruned.shift();
    while (pruned.length > 0 && pruned[pruned.length - 1].type === 'divider') pruned.pop();
    return pruned;
  }, [items]);

  // Compute org unit for carbon context header
  const { userOrgUnit } = useMemo(() => {
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
      {/* Compact title bar with collapse button — VS Code style */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 28,
          minHeight: 28,
          px: 0.75,
          borderBottom: '1px solid',
          borderColor: 'divider',
          flexShrink: 0,
        }}
      >
        <Typography
          noWrap
          sx={{
            fontSize: '0.6rem',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            color: 'text.secondary',
          }}
        >
          {title}
        </Typography>
        <Tooltip title="Collapse sidebar (Ctrl+B)" placement="bottom">
          <IconButton
            size="small"
            onClick={onCollapse}
            aria-label="Collapse sidebar"
            sx={{
              p: 0.25,
              opacity: 0.4,
              '&:hover': { opacity: 1, bgcolor: 'action.hover' },
            }}
          >
            <ChevronLeftIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Navigation items */}
      <List
        disablePadding
        sx={{
          flex: 1,
          overflow: 'auto',
          py: 0.5,
          px: 0.75,
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
            let lastWasGroup = false;

            items.forEach((item, index) => {
              if (!item.type && !item.path) return;

              // Divider → subtle gap (skip rendering, just add spacing)
              if (item.type === 'divider') {
                if (rendered.length > 0 && !lastWasGroup) {
                  rendered.push(
                    <Box key={`spacer-${index}`} sx={{ height: 6 }} />
                  );
                }
                return;
              }

              // Group header → ultra-compact label
              if (item.type === 'group') {
                rendered.push(
                  <Typography
                    key={`group-${item.label}`}
                    sx={{
                      fontSize: '0.575rem',
                      fontWeight: 500,
                      color: 'text.disabled',
                      letterSpacing: '0.04em',
                      px: 0.75,
                      pt: 0.75,
                      pb: 0.25,
                      display: 'block',
                    }}
                  >
                    {item.label}
                  </Typography>
                );
                lastWasGroup = true;
                return;
              }

              // Regular navigation items
              const Icon = item.icon;
              const itemPath = item.path ? item.path.replace(/\/+$|^\/+/, '') : '';
              const isActive = itemPath && (normalizedLocation === itemPath || normalizedLocation.startsWith(`${itemPath}/`));

              rendered.push(
                <Box
                  key={item.path}
                  onClick={() => onNavigate(item)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.75,
                    height: 28,
                    px: 0.75,
                    borderRadius: '5px',
                    cursor: 'pointer',
                    position: 'relative',
                    color: isActive ? 'primary.main' : 'text.secondary',
                    transition: 'all 0.12s ease',
                    '&:hover': {
                      bgcolor: 'action.hover',
                      color: isActive ? 'primary.main' : 'text.primary',
                    },
                    // Left-bar active indicator (VS Code / Linear style)
                    ...(isActive && {
                      bgcolor: (t) => t.palette.mode === 'light' ? 'rgba(14,165,233,0.07)' : 'rgba(56,189,248,0.1)',
                      '&::before': {
                        content: '""',
                        position: 'absolute',
                        left: 0,
                        top: 6,
                        bottom: 6,
                        width: 2.5,
                        borderRadius: '0 3px 3px 0',
                        bgcolor: 'primary.main',
                      },
                    }),
                  }}
                  title={item.label}
                >
                  <Icon sx={{ fontSize: 14, flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
                  <Typography
                    noWrap
                    sx={{
                      fontSize: '0.65rem',
                      fontWeight: isActive ? 600 : 400,
                      lineHeight: 1,
                    }}
                  >
                    {item.label}
                  </Typography>
                </Box>
              );
              lastWasGroup = false;
            });

            return rendered;
          })()
        )}
      </List>

      {/* Bottom context strip — org unit pill (org-scoped users only) */}
      {activeStudio === 'carbon' && userOrgUnit && !(user?.is_superuser || isGlobalAdminFlag) && (
        <Box
          sx={{
            flexShrink: 0,
            px: 0.75,
            py: 0.5,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              px: 0.75,
              py: 0.375,
              borderRadius: '5px',
              bgcolor: (t) => t.palette.mode === 'light' ? 'rgba(14,165,233,0.05)' : 'rgba(56,189,248,0.08)',
            }}
          >
            <LocationOnIcon sx={{ fontSize: 10, color: 'primary.main', flexShrink: 0 }} />
            <Typography
              noWrap
              sx={{ fontSize: '0.575rem', fontWeight: 500, color: 'text.secondary', lineHeight: 1 }}
              title={userOrgUnit}
            >
              {userOrgUnit}
            </Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
}
