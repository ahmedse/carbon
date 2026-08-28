// src/pages/carbon/CarbonConsolePage.jsx
// Carbon Console — Operational Status Board.
// Answers: "What is the state of our data right now? What needs attention?"
// NOT a navigation hub — the sidebar already handles navigation.

import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Grid, Typography, Card, CardContent, Stack, Chip, LinearProgress,
  Alert, Divider, Button, Tooltip, CircularProgress,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { fetchConsoleData } from '../../api/emissions';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import ActivityFeed from '../../components/Feedback/ActivityFeed';
import {
  CheckCircleOutline, ErrorOutline, WarningAmber, InfoOutlined,
  CalendarMonth, BarChart, Assignment, Speed, DataObject, Refresh,
  ArrowForward,
} from '@mui/icons-material';

function mapActivity(items) {
  return (items || []).map((it) => ({ ...it, module: it.module_name || it.module, action: it.action || 'calculation_completed' }));
}

// ── Compact status card ──────────────────────────────────────────────────────
function StatusCard({ label, value, unit, sub, color, icon, tooltip, onClick }) {
  const theme = useTheme();
  return (
    <Tooltip title={tooltip || ''} arrow placement="top">
      <Card
        variant="outlined"
        onClick={onClick}
        sx={{
          borderRadius: 1.5, height: '100%', cursor: onClick ? 'pointer' : 'default',
          borderColor: color ? `${theme.palette[color]?.main}40` : 'divider',
          transition: 'box-shadow 0.15s',
          '&:hover': onClick ? { boxShadow: 3, borderColor: `${theme.palette[color]?.main || theme.palette.primary.main}80` } : {},
        }}
      >
        <CardContent sx={{ p: '10px 14px', '&:last-child': { pb: '10px' } }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" mb={0.75}>
            <Box sx={{ color: color ? `${color}.main` : 'text.secondary', display: 'flex' }}>
              {React.cloneElement(icon, { sx: { fontSize: 18 } })}
            </Box>
            {onClick && <ArrowForward sx={{ fontSize: 14, color: 'text.disabled' }} />}
          </Stack>
          <Typography sx={{ fontSize: '1.25rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.1 }}>
            {value}
            {unit && <Typography component="span" sx={{ fontSize: '0.68rem', ml: 0.4, color: 'text.secondary', fontWeight: 500 }}>{unit}</Typography>}
          </Typography>
          <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.04em', mt: 0.25 }}>
            {label}
          </Typography>
          {sub && <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', mt: 0.125 }}>{sub}</Typography>}
        </CardContent>
      </Card>
    </Tooltip>
  );
}

// ── Section header ──────────────────────────────────────────────────────────
function SectionHead({ title, sub, action }) {
  return (
    <Stack direction="row" alignItems="baseline" justifyContent="space-between" mb={1}>
      <Box>
        <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'text.secondary' }}>
          {title}
        </Typography>
        {sub && <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>{sub}</Typography>}
      </Box>
      {action}
    </Stack>
  );
}

export default function CarbonConsolePage() {
  useDocumentTitle('Carbon Console');
  const navigate = useNavigate();
  const theme = useTheme();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { setData(await fetchConsoleData()); }
    catch (err) { setError(err.message || 'Failed to load console data'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const activity = useMemo(() => mapActivity(data?.recent_activity || []), [data]);

  if (loading) return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
      <CircularProgress size={40} />
    </Box>
  );
  if (error) return (
    <Box sx={{ p: 3 }}>
      <Alert severity="error" action={<Button size="small" onClick={load} startIcon={<Refresh fontSize="small" />}>Retry</Button>}>{error}</Alert>
    </Box>
  );

  const period = data?.active_period;
  const stats  = data?.stats || {};
  const alerts = data?.alerts || [];
  const dqAlerts = alerts.filter(a => a.type !== 'pending_submission');
  const pendingAlerts = alerts.filter(a => a.type === 'pending_submission');

  // Period status derived
  const periodStatusColor = !period ? 'default' : period.status === 'open' ? 'success' : period.status === 'locked' ? 'error' : 'warning';
  const periodStatusLabel = period?.status?.replace('_', ' ') || 'none';
  const daysLeft = period?.days_remaining;
  const daysLeftColor = daysLeft == null ? 'text.disabled' : daysLeft <= 14 ? theme.palette.error.main : daysLeft <= 30 ? theme.palette.warning.main : theme.palette.success.main;

  // Quality score color
  const qScore = Math.round(stats.avg_quality_score ?? 0);
  const qColor = qScore >= 80 ? 'success' : qScore >= 60 ? 'warning' : 'error';

  return (
    <Box sx={{ height: '100%', overflow: 'auto', p: 2.5 }}>

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <Box sx={{ mb: 2, pb: 1.5, borderBottom: `1px solid ${theme.palette.divider}` }}>
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" flexWrap="wrap" gap={1}>
          <Box>
            <Typography sx={{ fontSize: '1.1rem', fontWeight: 700, color: 'text.primary' }}>
              Carbon Console
            </Typography>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.25, lineHeight: 1.5 }}>
              Operational status board — period health, data completeness, DQ alerts, recent activity.
              Answers: <em>"What is the state of our data right now? What needs attention?"</em>
            </Typography>
          </Box>
          <Tooltip title="Refresh status">
            <Button size="small" variant="outlined" startIcon={<Refresh sx={{ fontSize: 14 }} />} onClick={load}
              sx={{ fontSize: '0.7rem', borderColor: 'divider', color: 'text.secondary', height: 28 }}>
              Refresh
            </Button>
          </Tooltip>
        </Stack>
      </Box>

      {/* ── Active period status ─────────────────────────────────────────── */}
      <Box sx={{ mb: 2.5 }}>
        <SectionHead
          title="Active Reporting Period"
          sub="The period currently accepting data entry and calculations"
          action={
            <Button size="small" sx={{ fontSize: '0.65rem', color: 'primary.main', p: 0, minWidth: 0 }}
              onClick={() => navigate('/carbon/reporting/periods')}>
              Manage →
            </Button>
          }
        />
        {!period
          ? (
            <Alert severity="warning" sx={{ fontSize: '0.78rem' }}
              action={<Button size="small" onClick={() => navigate('/carbon/reporting/periods')}>Create Period</Button>}>
              No active reporting period. Create one to start tracking emissions.
            </Alert>
          )
          : (
            <Card variant="outlined" sx={{ borderRadius: 1.5, borderColor: `${theme.palette[periodStatusColor]?.main || theme.palette.divider}50` }}>
              <CardContent sx={{ p: '12px 16px', '&:last-child': { pb: '12px' } }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'center' }} justifyContent="space-between" gap={1.5} flexWrap="wrap">
                  <Stack direction="row" alignItems="center" gap={1.5}>
                    <CalendarMonth sx={{ fontSize: 22, color: `${periodStatusColor}.main` }} />
                    <Box>
                      <Stack direction="row" alignItems="center" gap={1}>
                        <Typography sx={{ fontSize: '0.9rem', fontWeight: 700, color: 'text.primary' }}>{period.name}</Typography>
                        <Chip size="small" label={periodStatusLabel} color={periodStatusColor}
                          sx={{ fontSize: '0.6rem', height: 18, fontWeight: 700, textTransform: 'uppercase' }} />
                      </Stack>
                      <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', mt: 0.25 }}>
                        {period.start_date} → {period.end_date}
                        {daysLeft != null && (
                          <Typography component="span" sx={{ ml: 1.5, fontSize: '0.68rem', fontWeight: 600, color: daysLeftColor }}>
                            {daysLeft > 0 ? `${daysLeft} days remaining` : 'Period ended'}
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
                        sx={{ height: 6, borderRadius: 1, bgcolor: 'divider',
                          '& .MuiLinearProgress-bar': { bgcolor: daysLeftColor, borderRadius: 1 } }}
                      />
                      <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled', mt: 0.5, textAlign: 'right' }}>period progress</Typography>
                    </Box>
                  )}
                </Stack>
              </CardContent>
            </Card>
          )
        }
      </Box>

      {/* ── Data status KPIs ─────────────────────────────────────────────── */}
      <Box sx={{ mb: 2.5 }}>
        <SectionHead title="Data Status" sub="Current period data completeness and calculation health" />
        <Grid container spacing={1.25}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatusCard label="Total Emissions" value={(stats.total_emissions_tonnes ?? 0).toLocaleString()} unit="t CO₂e"
              sub="calculated to date" color="primary" icon={<BarChart />}
              onClick={() => navigate('/carbon/dashboard')}
              tooltip="Total verified CO₂e across all modules in the active period. Click to view Emissions Dashboard." />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatusCard label="Calculations" value={stats.total_calculations ?? 0} unit="records"
              sub={`across ${stats.total_tables ?? 0} tables`} color="info" icon={<DataObject />}
              onClick={() => navigate('/carbon/calculations')}
              tooltip="Total CO₂e calculation records. Each record = one activity row × emission factor. Click to inspect." />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatusCard label="Data Quality" value={`${qScore}%`} sub="profile completeness score"
              color={qColor} icon={<Speed />}
              tooltip="Data quality completeness score (0-100). Measures how many fields are filled vs required. Target: ≥80%." />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatusCard label="Active Modules" value={stats.total_modules ?? 0} unit="modules"
              sub={`${stats.total_tables ?? 0} data tables`} color="success" icon={<Assignment />}
              onClick={() => navigate('/carbon/my-data')}
              tooltip="Modules with active data entry tables. Click to go to My Data and manage your data." />
          </Grid>
        </Grid>
      </Box>

      {/* ── Alerts ───────────────────────────────────────────────────────── */}
      {alerts.length > 0 && (
        <Box sx={{ mb: 2.5 }}>
          <SectionHead title="Attention Required" sub={`${alerts.length} item${alerts.length !== 1 ? 's' : ''} need your attention`} />
          <Stack spacing={0.75}>
            {pendingAlerts.map((a, i) => (
              <Alert key={i} severity="info" icon={<InfoOutlined fontSize="small" />}
                sx={{ fontSize: '0.75rem', py: 0.5, '& .MuiAlert-icon': { py: 0.75 } }}
                action={<Button size="small" onClick={() => navigate('/carbon/my-data')}>View Data</Button>}>
                <strong>Pending rows:</strong> {a.pending_rows} rows awaiting submission — {a.message || 'complete your data entry'}
              </Alert>
            ))}
            {dqAlerts.map((a, i) => (
              <Alert key={i} severity="warning" icon={<WarningAmber fontSize="small" />}
                sx={{ fontSize: '0.75rem', py: 0.5, '& .MuiAlert-icon': { py: 0.75 } }}
                action={<Button size="small" onClick={() => navigate('/carbon/calculations')}>Inspect</Button>}>
                <strong>DQ Alert:</strong> {a.message || `Quality score ${a.score}% — below threshold`}
              </Alert>
            ))}
          </Stack>
        </Box>
      )}

      {alerts.length === 0 && period && (
        <Box sx={{ mb: 2.5 }}>
          <Alert severity="success" icon={<CheckCircleOutline fontSize="small" />}
            sx={{ fontSize: '0.75rem', py: 0.5, '& .MuiAlert-icon': { py: 0.75 } }}>
            No alerts — data collection is on track for this period.
          </Alert>
        </Box>
      )}

      {/* ── Recent activity ───────────────────────────────────────────────── */}
      {activity.length > 0 && (
        <Box sx={{ mb: 1 }}>
          <SectionHead title="Recent Activity" sub="Latest data entry, calculations, and verifications" />
          <Card variant="outlined" sx={{ borderRadius: 1.5 }}>
            <CardContent sx={{ p: '8px 12px', '&:last-child': { pb: '8px' } }}>
              <ActivityFeed items={activity} maxItems={8} emptyMessage="No recent activity" />
            </CardContent>
          </Card>
        </Box>
      )}

    </Box>
  );
}

