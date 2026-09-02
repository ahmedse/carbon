// src/apps/people/tabs/EmployeeOverviewTab.jsx
// Employee 360 — "Pulse View": lifecycle strip · required interventions · quick facts · mini-timeline.
// Designed from GOFSCO HRMS pain-points doc: Kuwait Labor Law compliance, KOC certifications,
// rotation statuses (1/1 2/1 3/1 5/1), Kuwaitization, EOSI, attendance permissions.
// No form here — editing is in the Profile edit mode (toggle in the Identity/Employment cards).
// Receives complete entityData including timelineEvents loaded at page startup.

import React, { useMemo, useState } from 'react';
import {
  Alert, Box, Button, Chip, Collapse, Grid, IconButton, Paper,
  Stack, Tooltip, Typography,
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import WorkHistoryIcon from '@mui/icons-material/WorkHistory';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import PaidIcon from '@mui/icons-material/Paid';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import PersonOffIcon from '@mui/icons-material/PersonOff';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import EditNoteIcon from '@mui/icons-material/EditNote';
import FlagIcon from '@mui/icons-material/Flag';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useTranslation } from 'react-i18next';
import {
  daysUntilExpiry, expiryUrgency, formatAmount, formatDate,
  leaveBalanceByType, totalLeaveBalance,
} from '../utils';

// ── Event kind config (mirrors EmployeeTimelineTab) ────────────────────
const EV_CFG = {
  hired:            { Icon: WorkHistoryIcon,  color: 'success', label: 'Joined' },
  transferred:      { Icon: SwapHorizIcon,    color: 'primary', label: 'Transferred' },
  promoted:         { Icon: TrendingUpIcon,   color: 'info',    label: 'Promoted' },
  salary_change:    { Icon: PaidIcon,         color: 'warning', label: 'Salary Changed' },
  grade_change:     { Icon: TrendingUpIcon,   color: 'info',    label: 'Grade Changed' },
  contract_renewed: { Icon: AssignmentIcon,   color: 'info',    label: 'Contract Renewed' },
  rotation_changed: { Icon: AutorenewIcon,    color: 'default', label: 'Rotation Changed' },
  deactivated:      { Icon: PersonOffIcon,    color: 'error',   label: 'Deactivated' },
  reactivated:      { Icon: PersonAddIcon,    color: 'success', label: 'Reactivated' },
  profile_updated:  { Icon: EditNoteIcon,     color: 'default', label: 'Profile Updated' },
};
const DEF_CFG = { Icon: EditNoteIcon, color: 'default', label: null };

// ── Lifecycle Strip ──────────────────────────────────────────────────────
function LifecycleStrip({ joinDate, timelineEvents }) {
  const { t } = useTranslation('people');

  const milestones = useMemo(() => {
    if (!joinDate) return [];
    const today = new Date();
    const joined = new Date(joinDate);

    const list = [{ date: joined, kind: 'hired', label: 'Joined', color: 'success' }];

    // Kuwait Labour Law: 6-month probation standard
    const probEnd = new Date(joined);
    probEnd.setMonth(probEnd.getMonth() + 6);
    if (probEnd < today) {
      list.push({ date: probEnd, kind: 'probation', label: 'Probation End', color: 'primary' });
    }

    // Key events from timeline (exclude profile_updated noise)
    const KEY_KINDS = new Set(['transferred', 'promoted', 'salary_change', 'contract_renewed', 'grade_change']);
    for (const ev of (timelineEvents || [])) {
      if (KEY_KINDS.has(ev.event_kind) && ev.effective_date) {
        const cfg = EV_CFG[ev.event_kind] || DEF_CFG;
        list.push({
          date: new Date(ev.effective_date),
          kind: ev.event_kind,
          label: cfg.label || ev.event_kind,
          color: cfg.color,
          event: ev,
        });
      }
    }

    list.push({ date: today, kind: 'today', label: 'Today', isToday: true, color: 'primary' });
    return list.sort((a, b) => a.date - b.date);
  }, [joinDate, timelineEvents]);

  if (milestones.length < 2) return null;

  const minMs = milestones[0].date.getTime();
  const maxMs = milestones[milestones.length - 1].date.getTime();
  const span = maxMs - minMs || 1;
  const pct = (ms) => ((ms - minMs) / span) * 100;

  return (
    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, mb: 1.5 }}>
      <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em', mb: 1.5 }}>
        Lifecycle
      </Typography>
      <Box sx={{ position: 'relative', height: 44, mx: 1 }}>
        {/* Track */}
        <Box sx={{ position: 'absolute', top: '36%', left: 0, right: 0, height: 2, bgcolor: 'divider' }} />

        {/* Milestones */}
        {milestones.map((m, i) => {
          const left = `${pct(m.date.getTime())}%`;
          const dotColor = m.isToday ? 'primary.main' : m.color === 'default' ? 'text.disabled' : `${m.color}.main`;
          return (
            <Tooltip
              key={i}
              title={`${m.label} · ${m.isToday ? 'Today' : formatDate(m.date.toISOString())}`}
              placement="top"
              arrow
            >
              <Box sx={{ position: 'absolute', left, top: '50%', transform: 'translate(-50%, -50%)', cursor: 'pointer' }}>
                <Box sx={{
                  width: m.isToday ? 13 : 9, height: m.isToday ? 13 : 9,
                  borderRadius: '50%',
                  bgcolor: dotColor,
                  border: m.isToday ? '2.5px solid white' : 'none',
                  boxShadow: m.isToday ? `0 0 0 2.5px ${dotColor}` : 'none',
                  transition: 'transform 0.15s',
                  '&:hover': { transform: 'scale(1.35)' },
                }} />
                <Typography sx={{
                  position: 'absolute', top: 14, left: '50%',
                  transform: 'translateX(-50%)',
                  fontSize: '0.5rem', color: m.isToday ? 'primary.main' : 'text.disabled',
                  fontWeight: m.isToday ? 700 : 400,
                  whiteSpace: 'nowrap',
                }}>
                  {m.isToday ? 'Now' : m.date.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' })}
                </Typography>
              </Box>
            </Tooltip>
          );
        })}
      </Box>
    </Paper>
  );
}

// ── Required Interventions ───────────────────────────────────────────────
function buildInterventions(emp, certifications, leaveEntitlements) {
  const list = [];
  const today = new Date().toISOString().slice(0, 10);
  const currentYear = new Date().getFullYear();
  const id = emp.empId ?? emp.id;

  // Cert expiry
  const myCerts = certifications.filter(c => c.employee === id);
  for (const cert of myCerts) {
    const u = expiryUrgency(cert.expiry_date);
    if (u === 'expired') {
      list.push({
        severity: 'error',
        message: `${cert.cert_type} expired ${Math.abs(daysUntilExpiry(cert.expiry_date))} days ago`,
        icon: ErrorOutlineIcon,
      });
    } else if (u === 'critical' || u === 'warning') {
      list.push({
        severity: 'warning',
        message: `${cert.cert_type} expiring in ${daysUntilExpiry(cert.expiry_date)} days`,
        icon: WarningAmberIcon,
      });
    }
  }

  // Missing civil ID — KOC compliance critical
  if (!emp.civil_id) {
    list.push({ severity: 'info', message: 'Civil ID not on file — required for KOC compliance', icon: InfoOutlinedIcon });
  }

  // Missing Arabic name — payroll requirement
  if (!emp.name_ar_given && !emp.name_ar_family) {
    list.push({ severity: 'info', message: 'Arabic name required for payroll records', icon: InfoOutlinedIcon });
  }

  // Leave overrun (any type)
  const myEnts = leaveEntitlements.filter(e => e.employee === id && e.year === currentYear);
  for (const ent of myEnts) {
    if (Number(ent.used_days) > Number(ent.entitled_days)) {
      const over = (Number(ent.used_days) - Number(ent.entitled_days)).toFixed(1);
      list.push({
        severity: 'warning',
        message: `${ent.leave_type} overrun by ${over} days`,
        icon: WarningAmberIcon,
      });
    }
  }

  return list;
}

function InterventionRow({ severity, message, icon: Icon }) {
  const colorMap = { error: 'error', warning: 'warning', info: 'info' };
  const c = colorMap[severity] || 'info';
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.875, py: 0.5, px: 0.875, borderRadius: 1, bgcolor: `${c}.50` }}>
      <Icon sx={{ fontSize: '0.875rem', color: `${c}.main`, flexShrink: 0 }} />
      <Typography sx={{ flex: 1, fontSize: '0.75rem', color: `${c}.dark` || 'text.primary' }}>{message}</Typography>
    </Box>
  );
}

// ── Quick Fact Chip ───────────────────────────────────────────────────────
function FactChip({ label, value, highlight }) {
  return (
    <Box sx={{
      display: 'inline-flex', flexDirection: 'column',
      px: 1, py: 0.5,
      border: '1px solid', borderColor: 'divider',
      borderRadius: 1.5, bgcolor: highlight ? 'primary.50' : 'background.paper',
      minWidth: 72, alignItems: 'center',
    }}>
      <Typography sx={{ fontSize: '0.5rem', color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{label}</Typography>
      <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: highlight ? 'primary.main' : 'text.primary', mt: 0.125 }}>{value ?? '—'}</Typography>
    </Box>
  );
}

// ── Mini-timeline ────────────────────────────────────────────────────────
function MiniEvent({ ev, isLast }) {
  const cfg = EV_CFG[ev.event_kind] || DEF_CFG;
  const theme_color = cfg.color;
  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: 16 }}>
        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: theme_color === 'default' ? 'text.disabled' : `${theme_color}.main`, flexShrink: 0, mt: 0.375 }} />
        {!isLast && <Box sx={{ flex: 1, width: 1, bgcolor: 'divider', mt: 0.25 }} />}
      </Box>
      <Box sx={{ flex: 1, pb: isLast ? 0 : 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.75 }}>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 500 }}>{cfg.label || ev.event_kind}</Typography>
          <Typography sx={{ fontSize: '0.625rem', color: 'text.disabled' }}>{formatDate(ev.effective_date)}</Typography>
        </Box>
        {ev.notes && <Typography sx={{ fontSize: '0.625rem', color: 'text.secondary', fontStyle: 'italic' }}>{ev.notes}</Typography>}
      </Box>
    </Box>
  );
}

// ── Leave Bar (compact) ───────────────────────────────────────────────────
function MiniLeaveBar({ label, used, entitled }) {
  const pct = entitled > 0 ? Math.min(100, (used / entitled) * 100) : 0;
  const balance = entitled - used;
  const isLow = balance >= 0 && balance < 3;
  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.125 }}>
        <Typography sx={{ fontSize: '0.6875rem', textTransform: 'capitalize' }}>{label.replace(/_/g, ' ')}</Typography>
        <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }}>{used}/{entitled}d</Typography>
      </Box>
      <Box sx={{ height: 4, bgcolor: 'action.hover', borderRadius: 0.5, overflow: 'hidden' }}>
        <Box sx={{ height: '100%', width: `${pct}%`, bgcolor: isLow ? 'warning.main' : 'primary.main', borderRadius: 0.5, transition: 'width 0.4s' }} />
      </Box>
    </Box>
  );
}

// ── Main Component ────────────────────────────────────────────────────────
export default function EmployeeOverviewTab({ entityData }) {
  const { t } = useTranslation('people');
  const emp = entityData || {};
  const id = emp.empId ?? emp.id;
  const today = new Date().toISOString().slice(0, 10);
  const currentYear = new Date().getFullYear();

  const [showAllInterventions, setShowAllInterventions] = useState(false);

  // ── Computed ─────────────────────────────────────────────
  const interventions = useMemo(
    () => buildInterventions(emp, emp.certifications || [], emp.leaveEntitlements || []),
    [emp],
  );

  const myEnts = useMemo(
    () => (emp.leaveEntitlements || []).filter(e => e.employee === id && e.year === currentYear),
    [emp.leaveEntitlements, id, currentYear],
  );
  const balanceByType = useMemo(() => leaveBalanceByType(myEnts), [myEnts]);
  const activeBenefits = useMemo(
    () => (emp.benefits || []).filter(b => b.employee === id && (!b.effective_end || b.effective_end >= today)),
    [emp.benefits, id, today],
  );
  const recentEvents = useMemo(
    () => (emp.timelineEvents || []).slice(0, 5),
    [emp.timelineEvents],
  );
  const lastPayslipNet = useMemo(() => {
    // Proxy from entityData if available; real value comes from Pay tab
    return null;
  }, []);

  const visibleInterventions = showAllInterventions ? interventions : interventions.slice(0, 3);

  return (
    <Box sx={{ p: 2 }}>

      {/* ─ Lifecycle Strip ─ */}
      <LifecycleStrip joinDate={emp.join_date} timelineEvents={emp.timelineEvents} />

      {/* ─ Required Interventions ─ */}
      {interventions.length > 0 && (
        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, mb: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <FlagIcon sx={{ fontSize: '0.8125rem', color: interventions.some(i => i.severity === 'error') ? 'error.main' : 'warning.main' }} />
              <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                Required Interventions
              </Typography>
            </Box>
            <Chip
              size="small"
              label={interventions.length}
              color={interventions.some(i => i.severity === 'error') ? 'error' : 'warning'}
              sx={{ height: 16, fontSize: '0.5625rem', fontWeight: 700 }}
            />
          </Box>
          <Stack spacing={0.5}>
            {visibleInterventions.map((iv, i) => <InterventionRow key={i} {...iv} />)}
          </Stack>
          {interventions.length > 3 && (
            <Button
              size="small"
              onClick={() => setShowAllInterventions(v => !v)}
              startIcon={<ExpandMoreIcon sx={{ transform: showAllInterventions ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />}
              sx={{ mt: 0.75, fontSize: '0.6875rem', textTransform: 'none', p: '2px 6px' }}
            >
              {showAllInterventions ? 'Show less' : `Show ${interventions.length - 3} more`}
            </Button>
          )}
        </Paper>
      )}

      {/* ─ Quick Facts + This Year ─ */}
      <Grid container spacing={1.5} sx={{ mb: 1.5 }}>

        {/* Quick Facts */}
        <Grid item xs={12} sm={6}>
          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, height: '100%' }}>
            <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.07em', mb: 1 }}>
              Quick Facts
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
              {emp.rotation && (
                <FactChip label="Rotation" value={emp.rotation} />
              )}
              {emp.kuwaitization && (
                <FactChip label="Kuwaitization" value="✓ KWT National" highlight />
              )}
              {emp.employment_type_code && (
                <FactChip label="Employment" value={emp.employment_type_code} />
              )}
              {emp.contract_type_code && (
                <FactChip label="Contract" value={emp.contract_type_code} />
              )}
              {emp.nationality_code && (
                <FactChip label="Nationality" value={emp.nationality_code} />
              )}
              {emp.nationality && !emp.nationality_code && (
                <FactChip label="Nationality" value={emp.nationality} />
              )}
              {!emp.rotation && !emp.employment_type_code && !emp.nationality_code && !emp.nationality && (
                <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>No classification data yet</Typography>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* This Year */}
        <Grid item xs={12} sm={6}>
          <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, height: '100%' }}>
            <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.07em', mb: 0.75 }}>
              {currentYear} Snapshot
            </Typography>
            {balanceByType.length > 0 ? (
              <Stack spacing={0.75}>
                {balanceByType.slice(0, 3).map(b => (
                  <MiniLeaveBar key={b.type} label={b.type} used={b.used} entitled={b.entitled} />
                ))}
              </Stack>
            ) : (
              <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>No leave entitlements for {currentYear}</Typography>
            )}
            <Box sx={{ display: 'flex', gap: 1.5, mt: 1, flexWrap: 'wrap' }}>
              <Box>
                <Typography sx={{ fontSize: '0.5rem', color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Benefits</Typography>
                <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>{activeBenefits.length} active</Typography>
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.5rem', color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Join Date</Typography>
                <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>{formatDate(emp.join_date)}</Typography>
              </Box>
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* ─ Recent Activity ─ */}
      {recentEvents.length > 0 && (
        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              Recent Activity
            </Typography>
            <Typography sx={{ fontSize: '0.5625rem', color: 'text.disabled' }}>see Timeline tab for full history</Typography>
          </Box>
          <Stack spacing={0}>
            {recentEvents.map((ev, i) => (
              <MiniEvent key={ev.id} ev={ev} isLast={i === recentEvents.length - 1} />
            ))}
          </Stack>
        </Paper>
      )}

      {recentEvents.length === 0 && interventions.length === 0 && (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, textAlign: 'center' }}>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
            No events recorded yet — the lifecycle strip will populate after the first payroll run or profile change.
          </Typography>
        </Paper>
      )}

    </Box>
  );
}
