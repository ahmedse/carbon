// src/apps/people/tabs/EmployeeTimelineTab.jsx
// Visual vertical timeline: events grouped by year, colored/iconized by event_kind.
// Each event shows effective_date, human-readable label, notes, and a salary diff
// when the event carries before/after salary data.

import React, { useEffect, useState } from 'react';
import { Alert, Box, Collapse, IconButton, Tooltip, Typography, useTheme } from '@mui/material';
import WorkHistoryIcon from '@mui/icons-material/WorkHistory';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import PaidIcon from '@mui/icons-material/Paid';
import GradeIcon from '@mui/icons-material/Grade';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import AssignmentIcon from '@mui/icons-material/Assignment';
import PersonOffIcon from '@mui/icons-material/PersonOff';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import EditNoteIcon from '@mui/icons-material/EditNote';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../../auth/AuthContext';
import { fetchEmployeeTimeline } from '../../../api/people';
import LoadingSkeleton from '../../../components/Page/LoadingSkeleton';
import EmptyState from '../../../components/Page/EmptyState';
import { formatDate, formatAmount } from '../utils';

// ── Event kind configuration ───────────────────────────────────

const EVENT_CFG = {
  hired:            { Icon: WorkHistoryIcon,  color: 'success', labelKey: 'eventKindHired' },
  transferred:      { Icon: SwapHorizIcon,    color: 'primary', labelKey: 'eventKindTransferred' },
  promoted:         { Icon: TrendingUpIcon,   color: 'info',    labelKey: 'eventKindPromoted' },
  salary_change:    { Icon: PaidIcon,         color: 'warning', labelKey: 'eventKindSalaryChange' },
  grade_change:     { Icon: GradeIcon,        color: 'info',    labelKey: 'eventKindGradeChange' },
  contract_renewed: { Icon: AssignmentIcon,   color: 'info',    labelKey: 'eventKindContractRenewed' },
  rotation_changed: { Icon: AutorenewIcon,    color: 'default', labelKey: 'eventKindRotationChanged' },
  deactivated:      { Icon: PersonOffIcon,    color: 'error',   labelKey: 'eventKindDeactivated' },
  reactivated:      { Icon: PersonAddIcon,    color: 'success', labelKey: 'eventKindReactivated' },
  profile_updated:  { Icon: EditNoteIcon,     color: 'default', labelKey: 'eventKindProfileUpdated' },
};
const DEFAULT_CFG = { Icon: EditNoteIcon, color: 'default', labelKey: null };

function dotBg(color, theme) {
  if (color === 'default') return theme.palette.action.disabledBackground;
  return theme.palette[color]?.main || theme.palette.primary.main;
}

function renderDiff(event) {
  const { before, after, event_kind } = event;
  if (!before && !after) return null;
  if (event_kind === 'salary_change') {
    const b = before?.basic_salary, a = after?.basic_salary;
    if (b !== a) return `${formatAmount(b)} → ${formatAmount(a)}`;
  }
  if (event_kind === 'transferred') {
    const b = before?.org_unit_id, a = after?.org_unit_id;
    if (b !== a) return `Org: ${b ?? '—'} → ${a ?? '—'}`;
  }
  return null;
}

// ── Single timeline event ──────────────────────────────────────

function TimelineEvent({ event, isLast, theme }) {
  const { t } = useTranslation('people');
  const [expanded, setExpanded] = useState(false);
  const cfg = EVENT_CFG[event.event_kind] || DEFAULT_CFG;
  const diff = renderDiff(event);
  const hasDiff = Boolean(diff);
  const dotColor = dotBg(cfg.color, theme);

  return (
    <Box sx={{ display: 'flex', gap: 1.5 }}>
      {/* Dot + connector */}
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, width: 28 }}>
        <Box sx={{
          width: 28, height: 28, borderRadius: '50%', bgcolor: dotColor,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: `0 0 0 3px ${dotColor}33`, zIndex: 1, flexShrink: 0,
        }}>
          <cfg.Icon sx={{ fontSize: '0.875rem', color: cfg.color === 'default' ? 'text.secondary' : 'white' }} />
        </Box>
        {!isLast && <Box sx={{ flex: 1, width: 2, bgcolor: 'divider', mt: 0.5, mb: 0.25 }} />}
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, pb: isLast ? 0 : 2, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, lineHeight: 1.3 }}>
              {cfg.labelKey ? t(cfg.labelKey) : event.event_kind}
            </Typography>
            <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
              {formatDate(event.effective_date)}
              {event.recorded_at && ` · recorded ${formatDate(event.recorded_at)}`}
            </Typography>
          </Box>
          {hasDiff && (
            <Tooltip title={expanded ? 'Hide changes' : 'Show changes'}>
              <IconButton size="small" onClick={() => setExpanded(v => !v)} sx={{ p: 0.25, mt: -0.25, flexShrink: 0 }}>
                {expanded ? <ExpandLessIcon sx={{ fontSize: '0.875rem' }} /> : <ExpandMoreIcon sx={{ fontSize: '0.875rem' }} />}
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {event.notes && (
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.25, fontStyle: 'italic' }}>
            {event.notes}
          </Typography>
        )}

        {hasDiff && (
          <Collapse in={expanded}>
            <Box sx={{ mt: 0.5, px: 1, py: 0.5, bgcolor: 'action.hover', borderRadius: 1, fontFamily: 'monospace', fontSize: '0.6875rem', color: 'text.secondary' }}>
              {diff}
            </Box>
          </Collapse>
        )}
      </Box>
    </Box>
  );
}

// ── Year group separator ───────────────────────────────────────

function YearSeparator({ year }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, mt: 0.5 }}>
      <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.1em', flexShrink: 0 }}>
        {year}
      </Typography>
      <Box sx={{ flex: 1, height: 1, bgcolor: 'divider' }} />
    </Box>
  );
}

// ── Main component ─────────────────────────────────────────────

export default function EmployeeTimelineTab({ entityData }) {
  const { t } = useTranslation('people');
  const { token } = useAuth();
  const theme = useTheme();
  const emp = entityData || {};

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!emp.id || !token) { setLoading(false); return; }
    setLoading(true);
    setError(null);
    fetchEmployeeTimeline(emp.id, token)
      .then(data => { if (!cancelled) setEvents(Array.isArray(data) ? data : []); })
      .catch(err => { if (!cancelled) setError(err?.message || t('timelineLoadError')); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [emp.id, token, t]);

  if (loading) return <Box sx={{ p: 2 }}><LoadingSkeleton variant="detail" /></Box>;
  if (error) return <Box sx={{ p: 2 }}><Alert severity="error">{error}</Alert></Box>;
  if (!events.length) return <Box sx={{ p: 2 }}><EmptyState title={t('timelineEmpty')} description={t('timelineEmptyDesc')} /></Box>;

  // Group by year (effective_date YYYY)
  const groups = {};
  for (const ev of events) {
    const yr = String(ev.effective_date || '').slice(0, 4) || '—';
    if (!groups[yr]) groups[yr] = [];
    groups[yr].push(ev);
  }
  const years = Object.keys(groups).sort((a, b) => b.localeCompare(a));

  return (
    <Box sx={{ p: 2 }}>
      {years.map(yr => {
        const evts = groups[yr];
        return (
          <Box key={yr}>
            <YearSeparator year={yr} />
            {evts.map((ev, i) => (
              <TimelineEvent key={ev.id} event={ev} isLast={i === evts.length - 1 && yr === years[years.length - 1]} theme={theme} />
            ))}
          </Box>
        );
      })}
    </Box>
  );
}
