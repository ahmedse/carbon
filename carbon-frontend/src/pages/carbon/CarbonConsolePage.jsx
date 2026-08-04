// src/pages/carbon/CarbonConsolePage.jsx
// Carbon Overview — enterprise landing page. Consumes GET /api/v1/emissions/console/
// All visuals from the shared component library (Phase 00). No ad-hoc cards/tables.

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Grid } from '@mui/material';
import { useAuth } from '../../auth/AuthContext';
import { fetchConsoleData } from '../../api/emissions';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { PageWrapper, SectionHeader, CollapsibleSection } from '../../theme/carbonDesign';
import PageHeader        from '../../components/Page/PageHeader';
import LoadingSkeleton   from '../../components/Page/LoadingSkeleton';
import ErrorAlert        from '../../components/Page/ErrorAlert';
import EmptyState        from '../../components/Page/EmptyState';
import StatCard          from '../../components/Cards/StatCard';
import WorkflowCard      from '../../components/Cards/WorkflowCard';
import PeriodBanner      from '../../components/Feedback/PeriodBanner';
import ActivityFeed      from '../../components/Feedback/ActivityFeed';

import {
  Dashboard as DashboardIcon,
  Description as ReportIcon,
  Storage as DataIcon,
  PrecisionManufacturing as FactorsIcon,
  Rule as RulesIcon,
  CalendarMonth as PeriodsIcon,
  BarChart as AnalyticsIcon,
  Inbox as InboxIcon,
} from '@mui/icons-material';

// ── Constants ─────────────────────────────────────────────────────────

const QUICK_ACTIONS = [
  { title: 'Dashboard', description: 'Organization-wide emissions, trends, and scope analysis', icon: <DashboardIcon />, path: '/carbon/dashboard', category: 'primary' },
  { title: 'My Data', description: 'Enter and manage activity data for emission sources', icon: <DataIcon />, path: '/carbon/my-data', category: 'primary' },
  { title: 'Reports', description: 'Generate compliance reports and export data', icon: <ReportIcon />, path: '/carbon/reporting/generate', category: 'primary' },
];

const ADMIN_TOOLS = [
  { title: 'Periods', description: 'Configure reporting periods and timelines', icon: <PeriodsIcon />, path: '/carbon/reporting/periods', admin: true },
  { title: 'Factors', description: 'Manage emission factors and GWP values', icon: <FactorsIcon />, path: '/carbon/admin/factors', admin: true },
  { title: 'Rules', description: 'Configure calculation rules and automation', icon: <RulesIcon />, path: '/carbon/admin/rules', admin: true },
];

const STAT_CARDS = [
  { title: 'Total Emissions', key: 'total_emissions_tonnes', color: 'primary',   icon: <AnalyticsIcon />, unit: 'tCO₂e' },
  { title: 'Modules',         key: 'total_modules',          color: 'success',   icon: <DataIcon /> },
  { title: 'Tables',          key: 'total_tables',           color: 'info',      icon: <FactorsIcon /> },
  { title: 'Quality',         key: 'avg_quality_score',      color: 'warning',   icon: <PeriodsIcon />,  unit: '%', fmt: (v) => v != null ? `${Math.round(v)}%` : 'N/A' },
  { title: 'Calculations',    key: 'total_calculations',      color: 'secondary', icon: <ReportIcon /> },
];

// ── Helpers ───────────────────────────────────────────────────────────

function mapActivity(items) {
  return (items || []).map((it) => ({ ...it, module: it.module_name || it.module, action: it.action || 'calculation_completed' }));
}

// ── Component ─────────────────────────────────────────────────────────

export default function CarbonConsolePage() {
  useDocumentTitle("Console");
  const navigate = useNavigate();
  const { user, availablePerspectives } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const isAdmin = user?.is_superuser || (availablePerspectives || []).some(p => p === 'admin' || p === 'carbon-admin');

  const load = async () => {
    setLoading(true); setError(null);
    try { setData(await fetchConsoleData()); }
    catch (err) { setError(err.message || 'Failed to load console data'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);  

  const period   = data?.active_period;
  const stats    = data?.stats;
  const alerts   = data?.alerts || [];
  const activity = useMemo(() => mapActivity(data?.recent_activity || []), [data]);

  // ── States ──────────────────────────────────────────────────────────

  if (loading) return <PageWrapper><LoadingSkeleton variant="console" /></PageWrapper>;
  if (error)   return <PageWrapper><PageHeader title="Carbon Overview" subtitle="Console dashboard" /><ErrorAlert message={error} onRetry={load} /></PageWrapper>;
  if (!period) return (
    <PageWrapper>
      <PageHeader title="Carbon Overview" subtitle="Console dashboard" />
      <EmptyState icon={<InboxIcon />} title="No reporting period configured"
        description="Create your first reporting period to start tracking emissions."
        actionLabel="Go to Periods" onAction={() => navigate('/carbon/reporting/periods')} />
    </PageWrapper>
  );

  // ── Data ────────────────────────────────────────────────────────────

  return (
    <PageWrapper>
      <PageHeader title="Carbon Overview"
        subtitle="Manage organizational carbon emissions with compact, enterprise-ready tracking."
        description="Enterprise carbon footprint dashboard showing emissions across Scope 1, 2, and 3 with trend analytics, data quality monitoring, and compliance tracking."
        badge={isAdmin ? { label: 'Admin', color: 'primary' } : undefined} />

      <PeriodBanner name={period.name} startDate={period.start_date} endDate={period.end_date}
        status={period.status} daysRemaining={period.days_remaining}
        onAction={() => navigate('/carbon/reporting/periods')} />

      {alerts.length > 0 && (
        <Grid container spacing={1} sx={{ mb: 2 }}>
          {alerts.slice(0, 4).map((a, i) => (
            <Grid size={{ xs: 6, sm: 6, md: 3 }} key={i}>
              <StatCard title={a.type === 'pending_submission' ? 'Pending' : 'DQ Alert'}
                value={a.type === 'pending_submission' ? a.pending_rows : a.score}
                unit={a.type === 'pending_submission' ? 'rows' : '%'}
                color={a.type === 'pending_submission' ? 'info' : 'warning'}
                tooltip={a.message || (a.type === 'pending_submission' ? 'Rows awaiting submission' : 'Data quality score')} />
            </Grid>
          ))}
        </Grid>
      )}

      {stats && (
        <Grid container spacing={1} sx={{ mb: 2 }}>
          {STAT_CARDS.map((sc) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={sc.key}>
              <StatCard title={sc.title} value={sc.fmt ? sc.fmt(stats[sc.key]) : (stats[sc.key] ?? 0)}
                unit={sc.unit} icon={sc.icon} color={sc.color}
                tooltip={`Total ${sc.title.toLowerCase()} across all modules in the current period`} />
            </Grid>
          ))}
        </Grid>
      )}

      <CollapsibleSection label="Quick Actions" defaultExpanded>
        <Grid container spacing={1}>
          {QUICK_ACTIONS.map((c) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={c.title}>
              <WorkflowCard icon={c.icon} title={c.title} description={c.description}
                onClick={() => navigate(c.path)} />
            </Grid>
          ))}
        </Grid>
      </CollapsibleSection>

      {isAdmin && (
        <CollapsibleSection label="Administration" defaultExpanded={false}>
          <Grid container spacing={1}>
            {ADMIN_TOOLS.map((c) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={c.title}>
                <WorkflowCard icon={c.icon} title={c.title} description={c.description}
                  onClick={() => navigate(c.path)} />
              </Grid>
            ))}
          </Grid>
        </CollapsibleSection>
      )}

      {activity.length > 0 && (
        <CollapsibleSection label="Recent Activity" defaultExpanded={false}>
          <ActivityFeed items={activity} maxItems={10} emptyMessage="No recent activity" />
        </CollapsibleSection>
      )}
    </PageWrapper>
  );
}
