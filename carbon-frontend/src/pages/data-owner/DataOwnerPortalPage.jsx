// src/pages/data-owner/DataOwnerPortalPage.jsx
// Data owner portal landing page - shows domains, quick stats, and recent activity

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchOwnerSummary,
  fetchOwnerAssets,
  fetchOwnerActivity,
} from '../../api/emissions';
import {
  Box,
  Container,
  Grid,
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Chip,
  CircularProgress,
  Alert,
  Paper,
  Divider,
  Stack,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Storage as StorageIcon,
  TrendingUp as TrendingIcon,
  Warning as WarningIcon,
  CheckCircle as PassIcon,
  Error as FailIcon,
} from '@mui/icons-material';

const QualityBadge = ({ status, score, theme }) => {
  const colorMap = {
    passing: { bg: theme.palette.success.light, color: theme.palette.success.dark, border: theme.palette.success.main },
    warning: { bg: theme.palette.warning.light, color: theme.palette.warning.dark, border: theme.palette.warning.main },
    failing: { bg: theme.palette.error.light, color: theme.palette.error.dark, border: theme.palette.error.main },
    unknown: { bg: theme.palette.action.disabledBackground, color: theme.palette.text.secondary, border: theme.palette.divider },
  };

  const colors = colorMap[status] || colorMap.unknown;
  const icons = {
    passing: <PassIcon sx={{ fontSize: 16, mr: 0.5 }} />,
    warning: <WarningIcon sx={{ fontSize: 16, mr: 0.5 }} />,
    failing: <FailIcon sx={{ fontSize: 16, mr: 0.5 }} />,
    unknown: <DashboardIcon sx={{ fontSize: 16, mr: 0.5 }} />,
  };

  return (
    <Chip
      icon={icons[status]}
      label={`${status.charAt(0).toUpperCase() + status.slice(1)} ${score ? `(${score}%)` : ''}`}
      sx={{
        backgroundColor: colors.bg,
        color: colors.color,
        border: `1px solid ${colors.border}`,
        fontWeight: 500,
        fontSize: '0.75rem',
      }}
    />
  );
};

const QuickStats = ({ assets, domainsCount, modulesWithData, modulesWithoutDataNames, theme }) => {
  return (
    <Grid container spacing={2} sx={{ mb: 4 }}>
      <Grid item xs={12} sm={6} md={3}>
        <Paper
          sx={{
            p: 2.5,
            textAlign: 'center',
            bgcolor: `${theme.palette.info.main}15`,
            borderLeft: `4px solid ${theme.palette.info.main}`,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600, color: theme.palette.info.dark }}>
            {assets?.length || 0}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Total Assets
          </Typography>
        </Paper>
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <Paper
          sx={{
            p: 2.5,
            textAlign: 'center',
            bgcolor: `${theme.palette.error.main}15`,
            borderLeft: `4px solid ${theme.palette.error.main}`,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600, color: theme.palette.error.dark }}>
            {assets?.filter(a => a.quality_status === 'failing').length || 0}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Needing Attention
          </Typography>
        </Paper>
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <Paper
          sx={{
            p: 2.5,
            textAlign: 'center',
            bgcolor: `${theme.palette.success.main}15`,
            borderLeft: `4px solid ${theme.palette.success.main}`,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600, color: theme.palette.success.dark }}>
            {domainsCount || 0}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Data Domains
          </Typography>
        </Paper>
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <Paper
          sx={{
            p: 2.5,
            textAlign: 'center',
            bgcolor: `${theme.palette.warning.main}15`,
            borderLeft: `4px solid ${theme.palette.warning.main}`,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600, color: theme.palette.warning.dark }}>
            {modulesWithoutDataNames?.length || 0}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Modules Missing Data
          </Typography>
        </Paper>
      </Grid>
    </Grid>
  );
};

const DomainCard = ({ domain, assetCount, avgQuality, navigate, theme }) => {
  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.3s ease',
        '&:hover': {
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
          transform: 'translateY(-2px)',
        },
        borderTop: `4px solid ${
          avgQuality >= 90 ? theme.palette.success.main : avgQuality >= 70 ? theme.palette.warning.main : theme.palette.error.main
        }`,
      }}
    >
      <CardContent sx={{ flexGrow: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
          {domain.name}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
          {domain.description || 'No description'}
        </Typography>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }} alignItems="center">
          <StorageIcon sx={{ fontSize: 16, color: theme.palette.text.secondary }} />
          <Typography variant="caption">{assetCount} asset(s)</Typography>
        </Stack>
        <QualityBadge
          status={avgQuality >= 90 ? 'passing' : avgQuality >= 70 ? 'warning' : 'failing'}
          score={Math.round(avgQuality)}
          theme={theme}
        />
      </CardContent>
      <Divider />
      <CardActions>
        <Button
          size="small"
          onClick={() => navigate(`/carbon/owner/assets?domain=${domain.id}`)}
          sx={{ color: theme.palette.success.main, fontWeight: 500 }}
        >
          View Assets →
        </Button>
      </CardActions>
    </Card>
  );
};

const RecentActivityFeed = ({ events, theme }) => {
  if (!events || events.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography color="text.secondary">No recent activity</Typography>
      </Box>
    );
  }

  return (
    <Stack spacing={2}>
      {events.slice(0, 5).map((event, idx) => (
        <Paper key={event.id} sx={{ p: 2, bgcolor: idx % 2 === 0 ? theme.palette.background.default : 'white' }}>
          <Stack direction="row" spacing={2} alignItems="flex-start">
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: theme.palette.success.main,
                mt: 1.2,
                flexShrink: 0,
              }}
            />
            <Box sx={{ flexGrow: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {new Date(event.timestamp).toLocaleDateString()} •{' '}
                {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                {event.entity_type} {event.action}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                by {event.user || 'system'}
              </Typography>
            </Box>
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
};

export default function DataOwnerPortalPage() {
  const { user, context, token } = useAuth();
  const navigate = useNavigate();
  const { showNotification } = useNotification();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const [domains, setDomains] = useState([]);
  const [assets, setAssets] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);

        const summaryRes = await fetchOwnerSummary(token);

        if (!summaryRes?.org_unit) {
          setError('no-scope');
          setLoading(false);
          return;
        }

        const assetsRes = await fetchOwnerAssets({}, token);
        const activityRes = await fetchOwnerActivity({ limit: 10 }, token);

        const orgDomain = {
          id: summaryRes.org_unit.id,
          name: summaryRes.org_unit.name,
          description: `${summaryRes.summary.total_modules} module(s) in scope`,
        };

        setDomains([orgDomain]);
        setAssets(Array.isArray(assetsRes) ? assetsRes : []);
        setEvents(Array.isArray(activityRes) ? activityRes : []);
        setError(null);
      } catch (err) {
        console.error('Error loading portal data:', err);
        setError('load-failed');
        showNotification({
          message: 'Failed to load portal data',
          type: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      loadData();
    }
  }, [token, showNotification]);

  if (loading) {
    return (
      <Container>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error === 'no-scope') {
    return (
      <Container>
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Alert severity="info" sx={{ maxWidth: 500, mx: 'auto' }}>
            <Typography variant="h6" sx={{ mb: 1 }}>No Data Scope Assigned</Typography>
            <Typography variant="body2">
              Contact your administrator to assign you to an organizational unit.
            </Typography>
          </Alert>
        </Box>
      </Container>
    );
  }

  // Calculate stats
  const domainsWithAssets = domains.filter(d =>
    assets.some(a => a.domain?.id === d.id)
  );
  const avgQualityByDomain = (domainId) => {
    const domainAssets = assets.filter(a => a.domain?.id === domainId);
    if (domainAssets.length === 0) return 0;
    const total = domainAssets.reduce((sum, a) => sum + (a.quality_score || 0), 0);
    return total / domainAssets.length;
  };

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 4 } }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <DashboardIcon sx={{ fontSize: 28, color: theme.palette.success.main }} />
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            My Data Portal
          </Typography>
        </Stack>
        <Typography color="text.secondary">
          Welcome, {user?.first_name || user?.username}. Here's your scoped view of {context?.org_units?.[0]?.name || 'your data'}.
        </Typography>
      </Box>

      {/* Quick Stats */}
      <QuickStats
        assets={assets}
        domainsCount={domainsWithAssets.length}
        modulesWithData={domainsWithAssets.length}
        modulesWithoutDataNames={domains.filter(d => !domainsWithAssets.includes(d)).map(d => d.name)}
      />

      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Domain Cards */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Data Domains ({domainsWithAssets.length})
          </Typography>
          {domainsWithAssets.length === 0 ? (
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography color="text.secondary">No domains with data yet</Typography>
            </Paper>
          ) : (
            <Grid container spacing={2}>
              {domainsWithAssets.map(domain => (
                <Grid item xs={12} sm={6} md={4} key={domain.id}>
                  <DomainCard
                    domain={domain}
                    assetCount={assets.filter(a => a.domain?.id === domain.id).length}
                    avgQuality={avgQualityByDomain(domain.id)}
                    navigate={navigate}
                  />
                </Grid>
              ))}
            </Grid>
          )}
        </Grid>

        {/* Recent Activity */}
        <Grid item xs={12} md={6}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Recent Activity
          </Typography>
          <RecentActivityFeed events={events} />
        </Grid>

        {/* Help & Navigation */}
        <Grid item xs={12} md={6}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Quick Navigation
          </Typography>
          <Stack spacing={2}>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                  📊 View Dashboard
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
                  See CO2e KPIs, data quality metrics, and submission status
                </Typography>
              </CardContent>
              <CardActions>
                <Button size="small" onClick={() => navigate('/carbon/owner/dashboard')}>
                  Go to Dashboard
                </Button>
              </CardActions>
            </Card>
            <Card>
              <CardContent>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                  📋 Browse Assets
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
                  Explore all assets and their data quality profiles
                </Typography>
              </CardContent>
              <CardActions>
                <Button size="small" onClick={() => navigate('/carbon/owner/assets')}>
                  View Assets
                </Button>
              </CardActions>
            </Card>
          </Stack>
        </Grid>
      </Grid>
    </Container>
  );
}
