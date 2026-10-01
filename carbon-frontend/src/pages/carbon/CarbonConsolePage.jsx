// Carbon Console — operational status. Typography is theme variants (RULE 8).

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box, Grid, Typography, Card, CardContent, Stack, Chip, LinearProgress,
  Alert, Button, Tooltip,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { fetchConsoleData } from '../../api/emissions';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import ActivityFeed from '../../components/Feedback/ActivityFeed';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import { MarketBasedAbsentAlert, Scope2MethodChip } from './Scope2Labels';
import {
  CheckCircleOutline, WarningAmber, InfoOutlined,
  CalendarMonth, BarChart, Assignment, Speed, DataObject, Refresh,
  ArrowForward,
} from '@mui/icons-material';

function mapActivity(items) {
  return (items || []).map((it) => ({ ...it, module: it.module_name || it.module, action: it.action || 'calculation_completed' }));
}

function StatusCard({ label, value, unit, sub, color, icon, tooltip, onClick, extra }) {
  const theme = useTheme();
  return (
    <Tooltip title={tooltip || ''} arrow placement="top">
      <Card
        variant="outlined"
        onClick={onClick}
        sx={{
          borderRadius: 1.5,
          height: '100%',
          cursor: onClick ? 'pointer' : 'default',
          borderColor: color ? `${theme.palette[color]?.main}` : 'divider',
        }}
      >
        <CardContent sx={{ p: '10px 14px', '&:last-child': { pb: '10px' } }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" mb={0.75}>
            <Box sx={{ color: color ? `${color}.main` : 'text.secondary', display: 'flex' }}>
              {icon}
            </Box>
            {onClick && <ArrowForward fontSize="small" color="disabled" />}
          </Stack>
          <Typography variant="h3" component="p" color="text.primary">
            {value}
            {unit && (
              <Typography component="span" variant="caption" sx={{ ml: 0.4 }} color="text.secondary">
                {unit}
              </Typography>
            )}
          </Typography>
          <Typography variant="overline" color="text.secondary" display="block">
            {label}
          </Typography>
          {sub && <Typography variant="caption" color="text.secondary" display="block">{sub}</Typography>}
          {extra}
        </CardContent>
      </Card>
    </Tooltip>
  );
}

function SectionHead({ title, sub, action }) {
  return (
    <Stack direction="row" alignItems="baseline" justifyContent="space-between" mb={1}>
      <Box>
        <Typography variant="overline" color="text.secondary">{title}</Typography>
        {sub && <Typography variant="caption" color="text.secondary" display="block">{sub}</Typography>}
      </Box>
      {action}
    </Stack>
  );
}

export default function CarbonConsolePage() {
  const { t } = useTranslation('emissions');
  useDocumentTitle(t('carbonConsole'));
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchConsoleData());
    } catch (err) {
      setError(err.message || t('console.loadFailed'));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const activity = useMemo(() => mapActivity(data?.recent_activity || []), [data]);

  if (loading) {
    return (
      <PageContainer>
        <LoadingSkeleton />
      </PageContainer>
    );
  }
  if (error) {
    return (
      <PageContainer>
        <Alert
          severity="error"
          action={<Button size="small" onClick={load}>{t('common:retry')}</Button>}
        >
          {error}
        </Alert>
      </PageContainer>
    );
  }

  const period = data?.active_period;
  const stats = data?.stats || {};
  const alerts = data?.alerts || [];
  const dqAlerts = alerts.filter((a) => a.type !== 'pending_submission');
  const pendingAlerts = alerts.filter((a) => a.type === 'pending_submission');

  const periodStatusColor = !period ? 'default' : period.status === 'open' ? 'success' : period.status === 'locked' ? 'error' : 'warning';
  const periodStatusLabel = period?.status?.replace('_', ' ') || t('console.none');
  const daysLeft = period?.days_remaining;
  const daysLeftColor = daysLeft == null ? 'text.secondary' : daysLeft <= 14 ? 'error.main' : daysLeft <= 30 ? 'warning.main' : 'success.main';

  const qScore = Math.round(stats.avg_quality_score ?? 0);
  const qColor = qScore >= 80 ? 'success' : qScore >= 60 ? 'warning' : 'error';
  const marketPresent = Boolean(stats?.by_scope2_method?.market_based?.present);

  return (
    <PageContainer sx={{ height: '100%', overflow: 'auto' }}>
      <PageHeader
        title={t('carbonConsole')}
        subtitle={t('consoleSubtitle')}
        actions={(
          <Tooltip title={t('refresh')}>
            <Button size="small" variant="outlined" startIcon={<Refresh />} onClick={load}>
              {t('refresh')}
            </Button>
          </Tooltip>
        )}
      />

      <MarketBasedAbsentAlert payload={stats} />

      <Box sx={{ mb: 2.5, mt: 1.5 }}>
        <SectionHead
          title={t('console.activePeriod')}
          sub={t('console.activePeriodSub')}
          action={(
            <Button size="small" onClick={() => navigate('/carbon/reporting/periods')}>
              {t('console.managePeriods')}
            </Button>
          )}
        />
        {!period
          ? (
            <Alert
              severity="warning"
              action={(
                <Button size="small" onClick={() => navigate('/carbon/reporting/periods')}>
                  {t('console.createPeriod')}
                </Button>
              )}
            >
              {t('console.noPeriod')}
            </Alert>
          )
          : (
            <Card variant="outlined" sx={{ borderRadius: 1.5 }}>
              <CardContent sx={{ p: '12px 16px', '&:last-child': { pb: '12px' } }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'center' }} justifyContent="space-between" gap={1.5} flexWrap="wrap">
                  <Stack direction="row" alignItems="center" gap={1.5}>
                    <CalendarMonth color={periodStatusColor === 'default' ? 'disabled' : periodStatusColor} />
                    <Box>
                      <Stack direction="row" alignItems="center" gap={1}>
                        <Typography variant="h6" component="p" color="text.primary">{period.name}</Typography>
                        <Chip size="small" label={periodStatusLabel} color={periodStatusColor} />
                      </Stack>
                      <Typography variant="body2" color="text.secondary">
                        {period.start_date}
                        {' → '}
                        {period.end_date}
                        {daysLeft != null && (
                          <Typography component="span" variant="body2" sx={{ ml: 1.5, color: daysLeftColor }}>
                            {daysLeft > 0 ? t('console.daysRemaining', { count: daysLeft }) : t('console.periodEnded')}
                          </Typography>
                        )}
                      </Typography>
                    </Box>
                  </Stack>
                  {daysLeft != null && daysLeft >= 0 && (
                    <Box sx={{ minWidth: 140 }}>
                      <LinearProgress
                        variant="determinate"
                        value={Math.min(Math.max(100 - (daysLeft / 365) * 100, 0), 100)}
                        color={daysLeft <= 14 ? 'error' : daysLeft <= 30 ? 'warning' : 'success'}
                        sx={{ height: 6, borderRadius: 1 }}
                      />
                      <Typography variant="caption" color="text.secondary" display="block" textAlign="right">
                        {t('console.periodProgress')}
                      </Typography>
                    </Box>
                  )}
                </Stack>
              </CardContent>
            </Card>
          )}
      </Box>

      <Box sx={{ mb: 2.5 }}>
        <SectionHead title={t('console.dataStatus')} sub={t('console.dataStatusSub')} />
        <Grid container spacing={1.25}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatusCard
              label={t('console.totalEmissions')}
              value={(stats.total_emissions_tonnes ?? 0).toLocaleString()}
              unit={t('chairman.unitTco2e')}
              sub={marketPresent ? t('console.headlineExcludesMarket') : t('scope2HeadlineLocation')}
              color="primary"
              icon={<BarChart fontSize="small" />}
              onClick={() => navigate('/carbon/dashboard')}
              extra={<Box sx={{ mt: 0.5 }}><Scope2MethodChip method="location_based" scope={2} /></Box>}
              tooltip={t('console.totalEmissionsTip')}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatusCard
              label={t('console.calculations')}
              value={stats.total_calculations ?? 0}
              unit={t('chairman.records')}
              sub={t('console.acrossTables', { count: stats.total_tables ?? 0 })}
              color="info"
              icon={<DataObject fontSize="small" />}
              onClick={() => navigate('/carbon/calculations')}
              tooltip={t('console.calculationsTip')}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatusCard
              label={t('console.dataQuality')}
              value={`${qScore}%`}
              sub={t('console.qualitySub')}
              color={qColor}
              icon={<Speed fontSize="small" />}
              tooltip={t('console.qualityTip')}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatusCard
              label={t('console.activeModules')}
              value={stats.total_modules ?? 0}
              unit={t('console.modules')}
              sub={t('console.dataTables', { count: stats.total_tables ?? 0 })}
              color="success"
              icon={<Assignment fontSize="small" />}
              onClick={() => navigate('/carbon/my-data')}
              tooltip={t('console.modulesTip')}
            />
          </Grid>
        </Grid>
      </Box>

      {alerts.length > 0 && (
        <Box sx={{ mb: 2.5 }}>
          <SectionHead
            title={t('console.attention')}
            sub={t('console.attentionCount', { count: alerts.length })}
          />
          <Stack spacing={0.75}>
            {pendingAlerts.map((a, i) => (
              <Alert
                key={`pending-${i}`}
                severity="info"
                icon={<InfoOutlined fontSize="small" />}
                action={<Button size="small" onClick={() => navigate('/carbon/my-data')}>{t('console.viewData')}</Button>}
              >
                {t('console.pendingRows', { count: a.pending_rows, message: a.message || t('console.completeEntry') })}
              </Alert>
            ))}
            {dqAlerts.map((a, i) => (
              <Alert
                key={`dq-${i}`}
                severity="warning"
                icon={<WarningAmber fontSize="small" />}
                action={<Button size="small" onClick={() => navigate('/carbon/calculations')}>{t('console.inspect')}</Button>}
              >
                {a.message || t('console.dqBelow', { score: a.score })}
              </Alert>
            ))}
          </Stack>
        </Box>
      )}

      {alerts.length === 0 && period && (
        <Box sx={{ mb: 2.5 }}>
          <Alert severity="success" icon={<CheckCircleOutline fontSize="small" />}>
            {t('console.noAlerts')}
          </Alert>
        </Box>
      )}

      {activity.length > 0 && (
        <Box sx={{ mb: 1 }}>
          <SectionHead title={t('console.recentActivity')} sub={t('console.recentActivitySub')} />
          <Card variant="outlined" sx={{ borderRadius: 1.5 }}>
            <CardContent sx={{ p: '8px 12px', '&:last-child': { pb: '8px' } }}>
              <ActivityFeed items={activity} maxItems={8} emptyMessage={t('console.noActivity')} />
            </CardContent>
          </Card>
        </Box>
      )}
    </PageContainer>
  );
}
