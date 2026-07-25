// src/pages/carbon/CarbonConsolePage.jsx
// Carbon Overview — compact, enterprise-grade landing page
// Uses shared carbonDesign.js tokens for consistent typography, spacing, and components.

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchActiveReportingPeriod, fetchOwnerSummary } from '../../api/emissions';
import {
  Box,
  Grid,
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Stack,
  Divider,
  useTheme,
} from '@mui/material';
import {
  EditNote as DataEntryIcon,
  Calculate as CalculateIcon,
  Assessment as ReportIcon,
  Science as FactorsIcon,
  CalendarMonth as PeriodsIcon,
  Dashboard as DashboardIcon,
  TrendingUp as AnalyticsIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import {
  PageWrapper,
  PageHeader,
  StatCard,
  FONT,
  SPACING,
  BORDER,
} from '../../theme/carbonDesign.jsx';

// ── Workflow Card ───────────────────────────────────────────────────────────
function WorkflowCard({ title, description, icon: Icon, color, onClick, isAdmin = false, disabled = false }) {
  const theme = useTheme();
  return (
    <Card
      variant="outlined"
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        borderLeft: `3px solid ${color}`,
        borderRadius: BORDER.radius,
        transition: 'box-shadow 0.15s ease, border-color 0.15s ease',
        '&:hover': disabled ? {} : {
          borderColor: color,
          boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
        },
      }}
      onClick={disabled ? undefined : onClick}
    >
      <CardContent sx={{ flexGrow: 1, p: SPACING.md, pb: `${SPACING.sm}px !important` }}>
        <Stack direction="row" spacing={SPACING.sm} alignItems="flex-start">
          <Box
            sx={{
              bgcolor: `${color}14`,
              borderRadius: 1,
              p: 0.75,
              display: 'flex',
              flexShrink: 0,
            }}
          >
            <Icon sx={{ fontSize: 20, color }} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={0.75} alignItems="center">
              <Typography sx={{ ...FONT.cardTitle }}>
                {title}
              </Typography>
              {isAdmin && (
                <Chip
                  label="Admin"
                  size="small"
                  sx={{
                    ...FONT.chip,
                    height: 16,
                    bgcolor: theme.palette.error.main + '20',
                    color: theme.palette.error.main,
                  }}
                />
              )}
            </Stack>
          </Box>
        </Stack>
        <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: SPACING.sm, lineHeight: 1.5 }}>
          {description}
        </Typography>
      </CardContent>
      <Divider />
      <CardActions sx={{ justifyContent: 'flex-end', px: SPACING.md, py: 0.75 }}>
        <Button size="small" sx={{ ...FONT.chip, color, fontWeight: 600 }} disabled={disabled}>
          {disabled ? 'Coming Soon' : 'Open →'}
        </Button>
      </CardActions>
    </Card>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────
export default function CarbonConsolePage() {
  const navigate = useNavigate();
  const theme = useTheme();
  const { context, user, availablePerspectives } = useAuth();
  const { showNotification } = useNotification();

  const [loading, setLoading] = useState(true);
  const [activePeriod, setActivePeriod] = useState(null);
  const [summary, setSummary] = useState(null);

  const isAdmin = user?.is_superuser || (availablePerspectives || []).includes('admin');
  const isDataOwner = isAdmin || (context?.org_units && context.org_units.length > 0);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [periodData, summaryData] = await Promise.all([
        fetchActiveReportingPeriod().catch(() => null),
        fetchOwnerSummary().catch(() => null),
      ]);
      setActivePeriod(periodData);
      setSummary(summaryData);
    } catch (err) {
      console.error('Error loading Carbon Overview:', err);
    } finally {
      setLoading(false);
    }
  };

  const workflows = [
    { title: 'Emissions Dashboard', description: 'Organization-wide emission trends, scope breakdowns, and year-over-year comparisons.', icon: DashboardIcon, color: theme.palette.primary.main, onClick: () => navigate('/carbon/dashboard') },
    { title: 'Analytics & Trends', description: 'Deep-dive into emission patterns, identify reduction opportunities, and track progress toward science-based targets.', icon: AnalyticsIcon, color: theme.palette.warning.main, onClick: () => navigate('/carbon/analytics') },
    { title: 'Data Entry', description: 'Record activity data for your organizational units — electricity, fuel, travel, and other emission sources.', icon: DataEntryIcon, color: theme.palette.success.main, onClick: () => navigate('/carbon/my-data'), role: 'carbon:data_owner' },
    { title: 'Emission Sources', description: 'Review your organizational unit\'s emission source assets, data quality scores, and submission status.', icon: CalculateIcon, color: theme.palette.info.main, onClick: () => navigate('/carbon/my-data?tab=sources'), role: 'carbon:data_owner' },
    { title: 'Generate Report', description: 'Create comprehensive emission reports by scope, category, or organizational unit. Export to CSV or JSON.', icon: ReportIcon, color: theme.palette.secondary.main, onClick: () => navigate('/carbon/reporting/generate'), role: 'carbon:analyst' },
    { title: 'Saved Reports', description: 'Access previously generated reports, re-run calculations, and download archived compliance documents.', icon: ReportIcon, color: theme.palette.info.main, onClick: () => navigate('/carbon/reporting/saved'), role: 'carbon:analyst' },
    { title: 'Emission Factors', description: 'Manage emission factors, GWP values, and calculation rules.', icon: FactorsIcon, color: theme.palette.error.main, onClick: () => navigate('/carbon/admin/factors'), isAdmin: true },
    { title: 'Calculation Rules', description: 'Define rules for automatic emission calculations. Map data table columns to emission factors.', icon: SettingsIcon, color: theme.palette.error.main, onClick: () => navigate('/carbon/admin/rules'), isAdmin: true },
    { title: 'Reporting Periods', description: 'Define fiscal years, quarters, and custom reporting periods. Manage period status and workflow transitions.', icon: PeriodsIcon, color: theme.palette.error.main, onClick: () => navigate('/carbon/reporting/periods'), isAdmin: true },
  ];

  const visibleWorkflows = workflows.filter(w => {
    if (isAdmin) return true;
    if (w.isAdmin) return false;
    if (w.role === 'carbon:data_owner') return isDataOwner;
    if (w.role === 'carbon:analyst') return true;
    return true;
  });

  if (loading) {
    return (
      <PageWrapper>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
          <CircularProgress size={32} />
        </Box>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper>
      <PageHeader
        title="Carbon Overview"
        subtitle={isDataOwner
          ? 'Manage your organizational unit\'s carbon emissions using GHG Protocol standards'
          : 'Manage organizational carbon emissions using GHG Protocol standards'}
      />

      {/* Active Period Alert */}
      {activePeriod ? (
        <Alert
          severity="info"
          icon={<PeriodsIcon sx={{ fontSize: 18 }} />}
          sx={{ mb: SPACING.lg, ...FONT.bodySmall, '& .MuiAlert-message': { ...FONT.bodySmall } }}
        >
          <strong>Active Period:</strong> {activePeriod.name} ({activePeriod.start_date} – {activePeriod.end_date})
          {activePeriod.status && ` — ${activePeriod.status.charAt(0).toUpperCase() + activePeriod.status.slice(1)}`}
        </Alert>
      ) : (
        <Alert severity="warning" sx={{ mb: SPACING.lg, ...FONT.bodySmall }}>
          No active reporting period. {isAdmin ? 'Create one in Reporting Periods.' : 'Contact your administrator.'}
        </Alert>
      )}

      {/* Quick Stats */}
      {summary && (
        <Grid container spacing={SPACING.sm} sx={{ mb: SPACING.lg }}>
          <Grid item xs={6} sm={3}>
            <StatCard label="Emission Sources" value={summary.modules?.length || 0} color={theme.palette.primary.main} icon={DataEntryIcon} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Data Tables" value={summary.total_tables || 0} color={theme.palette.success.main} icon={CalculateIcon} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Calculations" value={summary.total_calculations || 0} color={theme.palette.info.main} icon={AnalyticsIcon} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Data Quality" value={summary.avg_quality ? `${Math.round(summary.avg_quality)}%` : 'N/A'} color={theme.palette.warning.main} icon={SettingsIcon} />
          </Grid>
        </Grid>
      )}

      {/* Workflow Cards */}
      <Grid container spacing={SPACING.sm}>
        {visibleWorkflows.map((w, i) => (
          <Grid item xs={12} sm={6} md={4} key={i}>
            <WorkflowCard {...w} />
          </Grid>
        ))}
      </Grid>
    </PageWrapper>
  );
}
