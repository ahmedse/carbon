// File: src/shell/ShellSidebar.jsx
// Studio-specific sidebar navigation content with perspective awareness

import React, { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { Box, List, Typography, IconButton, Tooltip } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { ChevronStart } from '../i18n/DirectionalIcons';
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
import GroupsIcon from '@mui/icons-material/Groups';
import BadgeIcon from '@mui/icons-material/Badge';
import PersonIcon from '@mui/icons-material/Person';
import WorkIcon from '@mui/icons-material/Work';
import AccessTimeFilledIcon from '@mui/icons-material/AccessTimeFilled';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import SyncIcon from '@mui/icons-material/Sync';
import PaymentsIcon from '@mui/icons-material/Payments';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import RequestQuoteIcon from '@mui/icons-material/RequestQuote';
import GavelIcon from '@mui/icons-material/Gavel';
import TuneIcon from '@mui/icons-material/Tune';
import InboxIcon from '@mui/icons-material/Inbox';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import StairsIcon from '@mui/icons-material/Stairs';
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
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts';
import KeyboardIcon from '@mui/icons-material/Keyboard';
import CalculateIcon from '@mui/icons-material/Calculate';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ChatIcon from '@mui/icons-material/Chat';
import ForumIcon from '@mui/icons-material/Forum';
import PsychologyIcon from '@mui/icons-material/Psychology';
import MemoryIcon from '@mui/icons-material/Memory';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import HandymanIcon from '@mui/icons-material/Handyman';
import ExtensionIcon from '@mui/icons-material/Extension';
import CategoryIcon from '@mui/icons-material/Category';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import FeedbackIcon from '@mui/icons-material/Feedback';
import LoopIcon from '@mui/icons-material/Loop';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import SchoolIcon from '@mui/icons-material/School';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import SchemaIcon from '@mui/icons-material/Schema';
import TimelineIcon from '@mui/icons-material/Timeline';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import SearchIcon from '@mui/icons-material/Search';
import PolicyIcon from '@mui/icons-material/Policy';
import SupervisorAccountIcon from '@mui/icons-material/SupervisorAccount';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import CreateIcon from '@mui/icons-material/Create';
import EditNoteIcon from '@mui/icons-material/EditNote';
import RateReviewIcon from '@mui/icons-material/RateReview';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import ClassIcon from '@mui/icons-material/Class';
import VerifiedIcon from '@mui/icons-material/Verified';
import AccessibilityNewIcon from '@mui/icons-material/AccessibilityNew';
import LinkIcon from '@mui/icons-material/Link';
import { useAuth } from '../auth/AuthContext';
import { APP_REGISTRY } from '../apps/registry';
import { can, hasAppAccess } from '../authz';
import { useEnabledApps } from '../hooks/useEnabledApps';
import { MENU_ITEM_CAPABILITIES, LEARN_ACCESS, TEACH_ACCESS } from '../capabilities';
import { useTranslation } from 'react-i18next';
import { shellLabel, STUDIO_TITLE_KEYS } from '../i18n/shellLabels';

/** Resolve MUI icon component from manifest `icon` name (or label fallback). */
const MANIFEST_NAV_ICONS = {
  Dashboard: DashboardIcon,
  MenuBook: MenuBookIcon,
  Create: CreateIcon,
  EditNote: EditNoteIcon,
  RateReview: RateReviewIcon,
  Lightbulb: LightbulbIcon,
  School: SchoolIcon,
  Class: ClassIcon,
  Verified: VerifiedIcon,
  MonitorHeart: MonitorHeartIcon,
  Assessment: AssessmentIcon,
  TableChart: TableChartIcon,
  People: PeopleIcon,
  AccountBalanceWallet: AccountBalanceWalletIcon,
  Storage: StorageIcon,
  Home: HomeIcon,
  Assignment: AssignmentIcon,
  Timeline: TimelineIcon,
  Gavel: GavelIcon,
  Science: ScienceIcon,
  AccessibilityNew: AccessibilityNewIcon,
  Link: LinkIcon,
};

const GRADEVANCE_ITEM_ICONS = {
  Overview: DashboardIcon,
  'Pack library': MenuBookIcon,
  Library: MenuBookIcon,
  Proposals: LightbulbIcon,
  QA: ScienceIcon,
  Accessibility: AccessibilityNewIcon,
  LTI: LinkIcon,
};

const LEARN_ITEM_ICONS = {
  Home: HomeIcon,
  'My assignments': AssignmentIcon,
  Progress: TimelineIcon,
};

const TEACH_ITEM_ICONS = {
  Overview: DashboardIcon,
  Stems: ClassIcon,
  'Courses & stems': ClassIcon,
  Calibration: VerifiedIcon,
  'Marking queue': RateReviewIcon,
  Appeals: GavelIcon,
  Proposals: LightbulbIcon,
};

function resolveNavIcon(item, labelFallbackMap = {}) {
  if (item?.icon && MANIFEST_NAV_ICONS[item.icon]) {
    return MANIFEST_NAV_ICONS[item.icon];
  }
  if (item?.label && labelFallbackMap[item.label]) {
    return labelFallbackMap[item.label];
  }
  return DashboardIcon;
}

// UI-driven icon mapping for Carbon sidebar items
// This allows icons to be chosen at runtime without hardcoding
const CARBON_ITEM_ICONS = {
  'Chairman Overview':    AssessmentIcon,
  'Carbon Console':       DashboardIcon,
  'Overview':             DashboardIcon,
  'Emissions Dashboard':  BarChartIcon,
  'Analytics & Trends':   TimelineIcon,
  'Data Entry':           AddCircleOutlineIcon,
  'Reports':              AssessmentIcon,
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
  'Inventory Coverage':       TrackChangesIcon,
};

// People HRMS — filled / distinct glyphs (avoid thin-outline twins)
const PEOPLE_ITEM_ICONS = {
  'People':         GroupsIcon,
  'Positions':      WorkIcon,
  'Employees':      BadgeIcon,
  'Requests':       FactCheckIcon,
  'Attendance':     AccessTimeFilledIcon,
  'Leave':          EventAvailableIcon,
  'Certifications': WorkspacePremiumIcon,
  'Rotation':       SyncIcon,
  'Payroll':        PaymentsIcon,
  'Payslips':       ReceiptLongIcon,
  'Benefits':       VerifiedUserIcon,
  'Loans':          RequestQuoteIcon,
  'Policies':       GavelIcon,
  'App Config':     TuneIcon,
};

// My (ESS)
const MY_ITEM_ICONS = {
  'Dashboard':   PersonIcon,
  'My Leave':    EventAvailableIcon,
  'My Requests': AssignmentTurnedInIcon,
};

// Team (MSS)
const TEAM_ITEM_ICONS = {
  'Approvals Inbox': FactCheckIcon,
};

// Define sidebar content per studio
function getSidebarItems(studioId, helpApps = []) {
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
      // Catalog Studio IA — Discover → Browse → Govern → Reference → Integrate
      return [
        { type: 'group', label: 'Discover' },
        { label: 'Home', path: '/catalog', icon: DashboardIcon },
        { label: 'Search', path: '/catalog/search', icon: SearchIcon },
        { type: 'divider' },
        { type: 'group', label: 'Browse' },
        { label: 'Data Products', path: '/catalog/products', icon: TableChartIcon },
        { label: 'Asset Profiles', path: '/catalog/assets', icon: AssignmentIcon },
        { type: 'divider' },
        { type: 'group', label: 'Govern' },
        { label: 'Domains & Glossary', path: '/catalog/metadata', icon: EditIcon },
        { label: 'Data Quality', path: '/dq', icon: RuleIcon },
        { label: 'Access Policies', path: '/catalog/policies', icon: RuleIcon },
        { label: 'Audit Log', path: '/catalog/governance', icon: VerifiedUserIcon },
        { type: 'divider' },
        { type: 'group', label: 'Reference data' },
        { label: 'Reference Sets', path: '/catalog/mdm', icon: AccountTreeIcon },
        { label: 'Datasets', path: '/catalog/datasets', icon: StorageIcon },
        { type: 'divider' },
        { type: 'group', label: 'Connect & move' },
        { label: 'Connections', path: '/catalog/connections', icon: SecurityIcon },
        { label: 'Data Sources', path: '/catalog/sources', icon: StorageIcon },
        { label: 'Imports', path: '/catalog/imports', icon: UploadIcon },
        { label: 'Exports', path: '/catalog/exports', icon: DownloadIcon },
      ];
    
    case 'admin':
      return [
        { type: 'group', label: 'Access' },
        { label: 'Users', path: '/admin/users', icon: PeopleIcon, role: 'admin' },
        { label: 'Duties', path: '/admin/groups', icon: GroupIcon, role: 'admin' },
        { label: 'Assignments', path: '/admin/access', icon: AssignmentIcon, role: 'admin' },
        { label: 'Position profiles', path: '/admin/position-profiles', icon: WorkIcon, role: 'admin' },
        { label: 'Org Units', path: '/admin/org-units', icon: AccountTreeIcon, role: 'admin' },
        { type: 'divider' },
        { type: 'group', label: 'Trust' },
        { label: 'Field Policies', path: '/admin/catalog/field-policies', icon: SecurityIcon, role: 'admin' },
        { label: 'Audit Log', path: '/admin/audit', icon: HistoryIcon, role: 'admin' },
        { label: 'Excellence', path: '/admin/excellence', icon: StairsIcon, role: 'admin' },
        { label: 'Excellence runs', path: '/admin/excellence/runs', icon: StairsIcon, role: 'admin' },
        { label: 'Exemptions', path: '/admin/excellence/exemptions', icon: StairsIcon, role: 'admin' },
        { label: 'Initiatives', path: '/admin/excellence/initiatives', icon: StairsIcon, role: 'admin' },
        { label: 'Excellence standard', path: '/admin/excellence/standard', icon: StairsIcon, role: 'admin' },
        { label: 'Release rules', path: '/admin/excellence/rules', icon: StairsIcon, role: 'admin' },
        { type: 'divider' },
        { type: 'group', label: 'Apps' },
        { label: 'Registered Apps', path: '/admin/apps', icon: AppsIcon, role: 'admin' },
        { label: 'Role Registry', path: '/admin/role-matrix', icon: GridViewIcon, role: 'admin' },
        { type: 'divider' },
        { type: 'group', label: 'Platform' },
        { label: 'System Logs', path: '/admin/logs', icon: ArticleIcon, role: 'admin' },
        { label: 'Platform Config', path: '/admin/config', icon: SettingsIcon, role: 'admin' },
      ];

    case 'ai-admin':
      // ADR-0036 — Pulse Control Plane. Freeze: no new top-level peers.
      // Plan: docs/pulse/archive/PULSE-ADMIN-REMAKE.md
      return [
        { label: 'Command Center', path: '/admin/ai', icon: AutoAwesomeIcon, role: 'admin' },
        { label: 'Domain', path: '/admin/ai/domain', icon: RuleIcon, role: 'admin' },
        { label: 'Assets', path: '/admin/ai/assets', icon: PsychologyIcon, role: 'admin' },
        { label: 'Evidence', path: '/admin/ai/evidence', icon: HistoryIcon, role: 'admin' },
        { label: 'Learning', path: '/admin/ai/learning', icon: LoopIcon, role: 'admin' },
        { label: 'Platform', path: '/admin/ai/platform', icon: TuneIcon, role: 'admin' },
      ];
    
    case 'settings':
      return [
        { label: 'Account', path: '/settings?tab=account', icon: ManageAccountsIcon },
        { label: 'Security', path: '/settings?tab=security', icon: SecurityIcon },
        { label: 'Preferences', path: '/settings?tab=preferences', icon: SettingsIcon },
        { label: 'Shortcuts', path: '/settings?tab=shortcuts', icon: KeyboardIcon },
      ];
    
    case 'help':
      return [
        { label: 'Documentation', path: '/help', icon: DashboardIcon },
        { label: 'Feedback', path: '/feedback', icon: AssessmentIcon },
        ...(helpApps.length > 0
          ? [
              { type: 'divider' },
              { type: 'group', label: 'App Help' },
              ...helpApps.map(app => ({
                label: `${app.name} Help`,
                path: `/help/${app.id}`,
                icon: MenuBookIcon,
              })),
            ]
          : []),
      ];
    
    case 'apps':
    case 'healthy': {
      // Legacy 'apps' studio + Healthy Foods Factory — prefer manifest when present
      const healthyApp = APP_REGISTRY.find((m) => m.id === 'healthy');
      if (healthyApp?.navigation?.items?.length) {
        return healthyApp.navigation.items.map((item) => ({
          ...item,
          icon: DashboardIcon,
        }));
      }
      return [
        { label: 'Healthy Dashboard', path: '/apps/healthy', icon: DashboardIcon },
        { type: 'divider' },
        { type: 'group', label: 'Healthy Foods Factory' },
        { label: 'Loadout Sheet', path: '/apps/healthy/loadout', icon: TableChartIcon },
        { label: 'Rep Health', path: '/apps/healthy/reps', icon: PeopleIcon },
        { label: 'AR Queue', path: '/apps/healthy/collections', icon: AccountBalanceWalletIcon },
        { label: 'Slow Movers', path: '/apps/healthy/inventory', icon: StorageIcon },
      ];
    }

    case 'gradevance': {
      const gv = APP_REGISTRY.find((m) => m.id === 'gradevance');
      if (gv?.navigation?.items?.length) {
        return gv.navigation.items.map((item) => ({
          ...item,
          icon: resolveNavIcon(item, GRADEVANCE_ITEM_ICONS),
        }));
      }
      return [];
    }    
    case 'people': {
      // People app — read from manifest, resolve icons by label (mirrors case 'carbon')
      const peopleApp = APP_REGISTRY.find(m => m.id === 'people');
      if (peopleApp && peopleApp.navigation && peopleApp.navigation.items) {
        return peopleApp.navigation.items.map(item => ({
          ...item,
          icon: PEOPLE_ITEM_ICONS[item.label] || PeopleIcon,
        }));
      }
      return [];
    }

    case 'my': {
      // My app (employee self-service) — read from manifest, resolve icons by label
      const myApp = APP_REGISTRY.find(m => m.id === 'my');
      if (myApp && myApp.navigation && myApp.navigation.items) {
        return myApp.navigation.items.map(item => ({
          ...item,
          icon: MY_ITEM_ICONS[item.label] || PersonIcon,
        }));
      }
      return [];
    }

    case 'team': {
      const teamApp = APP_REGISTRY.find(m => m.id === 'team');
      if (teamApp && teamApp.navigation && teamApp.navigation.items) {
        return teamApp.navigation.items.map(item => ({
          ...item,
          icon: TEAM_ITEM_ICONS[item.label] || SupervisorAccountIcon,
        }));
      }
      return [];
    }

    case 'learn': {
      const learnApp = APP_REGISTRY.find((m) => m.id === 'learn');
      if (learnApp?.navigation?.items?.length) {
        return learnApp.navigation.items.map((item) => ({
          ...item,
          capability: LEARN_ACCESS,
          icon: resolveNavIcon(item, LEARN_ITEM_ICONS),
        }));
      }
      return [];
    }

    case 'teach': {
      const teachApp = APP_REGISTRY.find((m) => m.id === 'teach');
      if (teachApp?.navigation?.items?.length) {
        return teachApp.navigation.items.map((item) => ({
          ...item,
          capability: TEACH_ACCESS,
          icon: resolveNavIcon(item, TEACH_ITEM_ICONS),
        }));
      }
      return [];
    }

    default: {
      // Dynamic lookup: if this studioId is a manifest app, return its nav items.
      // This makes ALL future apps work with zero additional changes here.
      const manifest = APP_REGISTRY.find(m => m.id === studioId);
      if (manifest) {
        return manifest.navigation.items.map(item => ({
          ...item,
          icon: resolveNavIcon(item),
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
    'ai-admin': 'Pulse Control',
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
        return can(user, 'access_route', item.path.split('?')[0], authCtx);
      }
    }

    // Items with a label mapped in MENU_ITEM_CAPABILITIES
    if (item.label && MENU_ITEM_CAPABILITIES[item.label]) {
      return can(user, 'view_menu', item.label, authCtx);
    }

    // If item has a path, try route-based check (ignore query for CBAC)
    if (item.path && item.path !== '/') {
      return can(user, 'access_route', item.path.split('?')[0], authCtx);
    }

    // No capability requirement → visible to all authenticated users
    return true;
  });
}

export function ShellSidebar({ activeStudio, onNavigate, onCollapse }) {
  const { t } = useTranslation('shell');
  const theme = useTheme();
  const labelLineHeight = theme.direction === 'rtl' ? theme.typography.body1.lineHeight : 1;
  const { currentPerspective: _currentPerspective, availablePerspectives, isGlobalAdminFlag, userCapabilities, context, user } = useAuth();
  const location = useLocation();
  const { isAppEnabled } = useEnabledApps();

  // Build unified auth context for can() calls
  const authCtx = useMemo(() => ({
    perspectives: availablePerspectives,
    isGlobalAdminFlag,
    capabilities: userCapabilities,
    modules: context?.modules || [],
  }), [availablePerspectives, isGlobalAdminFlag, userCapabilities, context]);

  // Per-app help links (Help studio) — only for apps the admin enabled AND the user can access.
  const helpApps = useMemo(() => {
    if (activeStudio !== 'help') return [];
    return APP_REGISTRY
      .filter(m =>
        isAppEnabled(m.id) &&
        hasAppAccess(m.id, user, { perspectives: availablePerspectives, capabilities: userCapabilities, modules: context?.modules })
      )
      .map(m => ({ id: m.id, name: m.name }));
  }, [activeStudio, isAppEnabled, user, availablePerspectives, userCapabilities, context]);

  // Filter items based on capability-based access (CBAC)
  let items = getSidebarItems(activeStudio, helpApps);
  const titleKey = STUDIO_TITLE_KEYS[activeStudio];
  const title = titleKey ? t(titleKey) : getStudioTitle(activeStudio);

  // If in admin studios, gate with can() — only platform admins see them
  if ((activeStudio === 'admin' || activeStudio === 'ai-admin') && !can(user, 'access_route', '/admin/users', authCtx)) {
    items = []; // Hide all admin items for non-admin users
  }

  // Brand isolation: hide carbon sidebar items entirely when the carbon app is
  // disabled for this instance (FAIL-CLOSED — mirrors the studio filter in useShellState).
  if (activeStudio === 'carbon' && !isAppEnabled('carbon')) {
    items = [];
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
          height: theme.direction === 'rtl' ? 32 : 28,
          minHeight: theme.direction === 'rtl' ? 32 : 28,
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
            lineHeight: labelLineHeight,
            color: 'text.secondary',
          }}
        >
          {title}
        </Typography>
        <Tooltip title={t('ui.collapseSidebarShortcut')} placement="bottom">
          <IconButton
            size="small"
            onClick={onCollapse}
            aria-label={t('ui.collapseSidebar')}
            sx={{
              p: 0.25,
              opacity: 0.4,
              '&:hover': { opacity: 1, bgcolor: 'action.hover' },
            }}
          >
            <ChevronStart sx={{ fontSize: 14 }} />
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
              {t('ui.noItemsAvailable')}
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
                      fontSize: '0.6875rem',
                      fontWeight: 500,
                      color: 'text.disabled',
                      lineHeight: labelLineHeight,
                      letterSpacing: '0.04em',
                      px: 0.75,
                      pt: 0.75,
                      pb: 0.25,
                      display: 'block',
                    }}
                  >
                    {shellLabel(t, item.label)}
                  </Typography>
                );
                lastWasGroup = true;
                return;
              }

              // Regular navigation items — prefer longest matching path so
              // `/admin/ai` does not stay active on `/admin/ai/domain` (ADR-0036).
              // Paths may include a query (e.g. `/settings?tab=account`).
              const Icon = item.icon;
              const [itemPathname, itemQuery = ''] = (item.path || '').split('?');
              const itemPath = itemPathname.replace(/\/+$|^\/+/, '');
              const pathMatches = (candidate) =>
                candidate
                && (normalizedLocation === candidate
                  || normalizedLocation.startsWith(`${candidate}/`));
              const queryMatches = !itemQuery
                || location.search.replace(/^\?/, '') === itemQuery
                || new URLSearchParams(location.search).get('tab')
                  === new URLSearchParams(itemQuery).get('tab');
              const longerSiblingWins = items.some((other) => {
                if (!other.path || other.path === item.path) return false;
                const otherPath = other.path.split('?')[0].replace(/\/+$|^\/+/, '');
                return otherPath.length > itemPath.length && pathMatches(otherPath);
              });
              const isActive = pathMatches(itemPath) && queryMatches && !longerSiblingWins;

              rendered.push(
                <Box
                  key={item.path}
                  onClick={() => onNavigate(item)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.75,
                    height: theme.direction === 'rtl' ? 34 : 30,
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
                  title={shellLabel(t, item.label)}
                >
                  <Icon sx={{ fontSize: 16, flexShrink: 0, opacity: isActive ? 1 : 0.85 }} />
                  <Typography
                    noWrap
                    sx={{
                      fontSize: '0.75rem',
                      fontWeight: isActive ? 600 : 400,
                      lineHeight: labelLineHeight,
                    }}
                  >
                    {shellLabel(t, item.label)}
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
            <LocationOnIcon sx={{ fontSize: 12, color: 'primary.main', flexShrink: 0 }} />
            <Typography
              noWrap
              sx={{ fontSize: '0.6875rem', fontWeight: 500, color: 'text.secondary', lineHeight: labelLineHeight }}
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
