// src/pages/carbon/CarbonConsolePage.jsx
// Carbon Console - Main landing page for the Carbon app with workflow-based navigation

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchActiveReportingPeriod, fetchOwnerSummary } from '../../api/emissions';
import {
  Box,
  Container,
  Grid,
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Paper,
  Stack,
  Chip,
  Alert,
  CircularProgress,
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
  Info as InfoIcon,
} from '@mui/icons-material';

/**
 * Workflow card component
 */
const WorkflowCard = ({ title, description, icon: Icon, color, onClick, isAdmin = false, disabled = false }) => {
  const theme = useTheme();
  
  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.3s ease',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
        '&:hover': disabled ? {} : {
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
          transform: 'translateY(-4px)',
        },
        borderTop: `4px solid ${color}`,
      }}
      onClick={disabled ? undefined : onClick}
    >
      <CardContent sx={{ flexGrow: 1 }}>
        <Stack direction="row" spacing={2} alignItems="flex-start" sx={{ mb: 2 }}>
          <Box
            sx={{
              bgcolor: `${color}15`,
              borderRadius: 2,
              p: 1.5,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Icon sx={{ fontSize: 32, color }} />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {title}
              </Typography>
              {isAdmin && (
                <Chip
                  label="Admin"
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.65rem',
                    bgcolor: theme.palette.error.light,
                    color: theme.palette.error.dark,
                  }}
                />
              )}
            </Stack>
          </Box>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>
          {description}
        </Typography>
      </CardContent>
      <Divider />
      <CardActions sx={{ justifyContent: 'flex-end', px: 2, py: 1.5 }}>
        <Button size="small" sx={{ color, fontWeight: 600 }} disabled={disabled}>
          {disabled ? 'Coming Soon' : 'Open →'}
        </Button>
      </CardActions>
    </Card>
  );
};

/**
 * Quick stat card
 */
const StatCard = ({ label, value, color, icon: Icon }) => {
  return (
    <Paper
      sx={{
        p: 2.5,
        textAlign: 'center',
        bgcolor: `${color}10`,
        borderLeft: `4px solid ${color}`,
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" justifyContent="center" sx={{ mb: 1 }}>
        <Icon sx={{ fontSize: 20, color }} />
        <Typography variant="h5" sx={{ fontWeight: 600, color }}>
          {value}
        </Typography>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
        {label}
      </Typography>
    </Paper>
  );
};

/**
 * Main Carbon Console Page
 */
export default function CarbonConsolePage() {
  const navigate = useNavigate();
  const theme = useTheme();
  const { context, user } = useAuth();
  const { showNotification } = useNotification();
  
  const [loading, setLoading] = useState(true);
  const [activePeriod, setActivePeriod] = useState(null);
  const [summary, setSummary] = useState(null);

  const isAdmin = user?.is_superuser || context?.available_perspectives?.includes('admin');

  useEffect(() => {
    loadData();
  }, []);

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
      console.error('Error loading Carbon Console data:', err);
    } finally {
      setLoading(false);
    }
  };

  const isDataOwner = context?.org_units && context.org_units.length > 0;

  const workflows = [
    // ── Measure (all roles) ──
    {
      title: 'Emissions Dashboard',
      description: 'View organization-wide emission trends, scope breakdowns, and year-over-year comparisons. Monitor your carbon footprint at a glance.',
      icon: DashboardIcon,
      color: theme.palette.primary.main,
      onClick: () => navigate('/carbon/dashboard'),
    },
    {
      title: 'Analytics & Trends',
      description: 'Deep-dive into emission patterns, identify reduction opportunities, and track progress toward science-based targets.',
      icon: AnalyticsIcon,
      color: theme.palette.warning.main,
      onClick: () => navigate('/dashboards/analytics'),
    },

    // ── My Data (data owners) ──
    {
      title: 'Data Entry',
      description: 'Record activity data for your organizational units — electricity, fuel, travel, and other emission sources.',
      icon: DataEntryIcon,
      color: theme.palette.success.main,
      onClick: () => navigate('/carbon/data-entry'),
      role: 'carbon:data_owner',
    },
    {
      title: 'Emission Sources',
      description: 'Review your organizational unit\'s emission source assets, data quality scores, and submission status.',
      icon: CalculateIcon,
      color: theme.palette.info.main,
      onClick: () => navigate('/carbon/owner/assets'),
      role: 'carbon:data_owner',
    },

    // ── Reporting (analyst + admin) ──
    {
      title: 'Generate Report',
      description: 'Create comprehensive emission reports by scope, category, or organizational unit. Export to CSV or JSON for regulatory compliance.',
      icon: ReportIcon,
      color: theme.palette.secondary.main,
      onClick: () => navigate('/carbon/reporting/generate'),
      role: 'carbon:analyst',
    },
    {
      title: 'Saved Reports',
      description: 'Access previously generated reports, re-run calculations, and download archived compliance documents.',
      icon: ReportIcon,
      color: theme.palette.info.main,
      onClick: () => navigate('/carbon/reporting/saved'),
      role: 'carbon:analyst',
    },

    // ── Configuration (admin only) ──
    {
      title: 'Emission Factors',
      description: 'Manage emission factors, GWP values, and calculation rules. Configure automatic emission calculations for data tables.',
      icon: FactorsIcon,
      color: theme.palette.error.main,
      onClick: () => navigate('/carbon/admin/factors'),
      isAdmin: true,
    },
    {
      title: 'Calculation Rules',
      description: 'Define rules for automatic emission calculations. Map data table columns to emission factors and configure formulas.',
      icon: SettingsIcon,
      color: theme.palette.error.main,
      onClick: () => navigate('/carbon/admin/rules'),
      isAdmin: true,
    },
    {
      title: 'Reporting Periods',
      description: 'Define fiscal years, quarters, and custom reporting periods. Manage period status and workflow transitions.',
      icon: PeriodsIcon,
      color: theme.palette.error.main,
      onClick: () => navigate('/carbon/reporting/periods'),
      isAdmin: true,
    },
  ];

  // Filter workflows: admin sees all, data_owner sees role-appropriate, analyst sees analyst+
  const visibleWorkflows = workflows.filter(w => {
    if (isAdmin) return true;
    if (w.isAdmin) return false;
    if (w.role === 'carbon:data_owner') return isDataOwner;
    if (w.role === 'carbon:analyst') return true; // analysts see reporting items
    return true; // no role restriction = visible to all
  });

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
          Carbon Overview
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {isDataOwner
            ? 'Manage your organizational unit\'s carbon emissions using GHG Protocol standards'
            : 'Manage organizational carbon emissions using GHG Protocol standards'}
        </Typography>
      </Box>

      {/* Active Period Alert */}
      {activePeriod ? (
        <Alert
          severity="info"
          icon={<PeriodsIcon />}
          sx={{ mb: 3 }}
        >
          <strong>Active Reporting Period:</strong> {activePeriod.name} ({activePeriod.start_date} to {activePeriod.end_date})
          {activePeriod.status && ` — Status: ${activePeriod.status.charAt(0).toUpperCase() + activePeriod.status.slice(1)}`}
        </Alert>
      ) : (
        <Alert severity="warning" sx={{ mb: 3 }}>
          No active reporting period. {isAdmin ? 'Create one in Reporting Periods.' : 'Contact your administrator.'}
        </Alert>
      )}

      {/* Quick Stats */}
      {summary && (
        <Grid container spacing={2} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              label="Emission Sources"
              value={summary.modules?.length || 0}
              color={theme.palette.primary.main}
              icon={DataEntryIcon}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              label="Data Tables"
              value={summary.total_tables || 0}
              color={theme.palette.success.main}
              icon={CalculateIcon}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              label="Total Calculations"
              value={summary.total_calculations || 0}
              color={theme.palette.info.main}
              icon={AnalyticsIcon}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              label="Data Quality"
              value={summary.avg_quality ? `${Math.round(summary.avg_quality)}%` : 'N/A'}
              color={theme.palette.warning.main}
              icon={InfoIcon}
            />
          </Grid>
        </Grid>
      )}

      {/* Workflows Grid */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
          Workflows
        </Typography>
        <Grid container spacing={3}>
          {visibleWorkflows.map((workflow, index) => (
            <Grid item xs={12} sm={6} md={4} key={index}>
              <WorkflowCard {...workflow} />
            </Grid>
          ))}
        </Grid>
      </Box>

      {/* Getting Started Guide */}
      <Paper sx={{ p: 3, bgcolor: `${theme.palette.primary.main}08` }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
          Getting Started with Carbon
        </Typography>
        <Stack spacing={1.5}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                bgcolor: theme.palette.primary.main,
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.875rem',
                mr: 2,
                flexShrink: 0,
              }}
            >
              1
            </Box>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                Set up your organizational structure
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Define organizational units, emission sources (modules), and data collection boundaries
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                bgcolor: theme.palette.primary.main,
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.875rem',
                mr: 2,
                flexShrink: 0,
              }}
            >
              2
            </Box>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                Configure emission factors and calculation rules
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {isAdmin
                  ? 'Set up emission factors, GWP values, and automatic calculation rules for your data tables'
                  : 'Your administrator will configure emission factors and calculation rules'}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                bgcolor: theme.palette.primary.main,
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.875rem',
                mr: 2,
                flexShrink: 0,
              }}
            >
              3
            </Box>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                Enter activity data
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Record electricity usage, fuel consumption, travel, and other emission activities
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                bgcolor: theme.palette.primary.main,
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 600,
                fontSize: '0.875rem',
                mr: 2,
                flexShrink: 0,
              }}
            >
              4
            </Box>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                Calculate emissions and generate reports
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Trigger calculations, review results, and generate compliance reports
              </Typography>
            </Box>
          </Box>
        </Stack>
      </Paper>
    </Container>
  );
}
