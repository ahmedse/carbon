// src/components/ai/ScheduleDialog.jsx
// W6-E F-29 — create/edit a run schedule for a plan template. The operator
// picks an outcome cadence (once / daily / weekly / monthly) and a time; the
// form shows a plain-language preview (RULE_23 — "Every day at 9:00 AM", never
// a bare cron string) and progressive-discloses the raw cron for power users.
//
// The SERVER-SUPPLIED `preview` string on a saved schedule remains the single
// source of truth in the list (see ScheduleList). This dialog computes a
// provisional preview from the form so the operator sees the outcome *before*
// saving; a past-time one-off fails inline and disables Save.
//
// Theme tokens only (RULE_8); compact density (RULE_3).
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import Autocomplete from '@mui/material/Autocomplete';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

/** Cadence presets (RULE_23 — outcome terms, never "cron"/"schedule expression"). */
export const CADENCES = [
  { value: 'once', label: 'Once' },
  { value: 'daily', label: 'Every day' },
  { value: 'weekly', label: 'Every week' },
  { value: 'monthly', label: 'Every month' },
];

/** Cron day-of-week (0=Sunday … 6=Saturday), matching the backend contract. */
export const WEEKDAYS = [
  { value: 0, label: 'Sunday' },
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: 'Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
];

/** 12-hour clock, mirrors the backend `_format_clock` ("9:00 AM" / "2:00 PM"). */
export function formatClock(hour, minute) {
  const h = Number(hour) || 0;
  const m = Number(minute) || 0;
  const ampm = h < 12 ? 'AM' : 'PM';
  let h12 = h % 12;
  if (h12 === 0) h12 = 12;
  return `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
}

/** English ordinal for a day-of-month ("1" → "1st"), mirrors backend. */
export function ordinal(n) {
  const num = Number(n) || 0;
  if (num >= 11 && num <= 13) return `${num}th`;
  const suffix = { 1: 'st', 2: 'nd', 3: 'rd' }[num % 10] || 'th';
  return `${num}${suffix}`;
}

/** Build a standard 5-field cron expression for a recurring cadence. */
export function buildCron(cadence, { hour = 9, minute = 0, weekday = 1, dayOfMonth = 1 } = {}) {
  const h = Number(hour) || 0;
  const m = Number(minute) || 0;
  if (cadence === 'daily') return `${m} ${h} * * *`;
  if (cadence === 'weekly') return `${m} ${h} * * ${Number(weekday) || 0}`;
  if (cadence === 'monthly') return `${m} ${h} ${Number(dayOfMonth) || 1} * *`;
  return null;
}

/**
 * Provisional plain-language preview for the form (RULE_23). One-off reads the
 * local date/time; recurring reads the cadence + time. The saved schedule's
 * server `preview` supersedes this in the list.
 */
export function buildSchedulePreview(cadence, { runAt, hour = 9, minute = 0, weekday = 1, dayOfMonth = 1 } = {}) {
  if (cadence === 'once') {
    if (!runAt) return 'Once';
    const d = new Date(runAt);
    if (Number.isNaN(d.getTime())) return 'Once';
    const ymd = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return `Once on ${ymd} at ${formatClock(d.getHours(), d.getMinutes())}`;
  }
  const time = formatClock(hour, minute);
  if (cadence === 'daily') return `Every day at ${time}`;
  if (cadence === 'weekly') {
    const wd = WEEKDAYS.find((w) => w.value === (Number(weekday) || 0));
    return `Every ${wd ? wd.label : 'Monday'} at ${time}`;
  }
  if (cadence === 'monthly') return `Every ${ordinal(dayOfMonth)} of the month at ${time}`;
  return 'Once';
}

/** Best-effort parse of a 5-field cron into cadence + time/day (for edit seeding). */
export function parseCron(expr) {
  const fields = String(expr || '').trim().split(/\s+/);
  if (fields.length !== 5) return null;
  const [minute, hour, dom, month, dow] = fields;
  const h = Number(hour);
  const m = Number(minute);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return null;
  if (dom === '*' && month === '*') {
    if (dow === '*') return { cadence: 'daily', hour: h, minute: m };
    if (/^\d+$/.test(dow)) {
      const w = Number(dow);
      return { cadence: 'weekly', hour: h, minute: m, weekday: w === 7 ? 0 : w };
    }
  }
  if (dow === '*' && month === '*' && /^\d+$/.test(dom)) {
    return { cadence: 'monthly', hour: h, minute: m, dayOfMonth: Number(dom) };
  }
  return { cadence: 'daily', hour: h, minute: m };
}

/** Format a datetime-local value from a Date (YYYY-MM-DDTHH:mm, local). */
function toLocalInput(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

/**
 * Schedule dialog — create (Schedule action on a template) or edit.
 * @param {object} props
 * @param {boolean} props.open
 * @param {object|null} [props.schedule] - existing schedule (edit mode)
 * @param {object|null} [props.template] - template being scheduled (create mode)
 * @param {boolean} [props.busy] - a save is in flight
 * @param {function} [props.onSave] - (fields) => void, { name, cron_expr, run_at }
 * @param {function} [props.onClose]
 */
export default function ScheduleDialog({ open, schedule, template, busy, onSave, onClose }) {
  const [name, setName] = useState('');
  const [cadence, setCadence] = useState('once');
  const [runAt, setRunAt] = useState('');
  const [time, setTime] = useState('09:00');
  const [weekday, setWeekday] = useState(1);
  const [dayOfMonth, setDayOfMonth] = useState(1);
  const [showCron, setShowCron] = useState(false);

  // Seed form state whenever the dialog opens (create or edit).
  useEffect(() => {
    if (!open) return;
    setName(schedule?.name || template?.name || '');
    const parsed = schedule?.cron_expr ? parseCron(schedule.cron_expr) : null;
    if (schedule?.run_at) {
      setCadence('once');
      const d = new Date(schedule.run_at);
      setRunAt(Number.isNaN(d.getTime()) ? '' : toLocalInput(d));
    } else if (parsed) {
      setCadence(parsed.cadence);
      setTime(`${String(parsed.hour).padStart(2, '0')}:${String(parsed.minute).padStart(2, '0')}`);
      if (parsed.weekday !== undefined) setWeekday(parsed.weekday);
      if (parsed.dayOfMonth !== undefined) setDayOfMonth(parsed.dayOfMonth);
    } else {
      setCadence('once');
      setRunAt('');
    }
    setShowCron(false);
  }, [open, schedule, template]);

  const [hour = 9, minute = 0] = (time || '').split(':').map((n) => Number(n));
  const cronExpr = cadence === 'once' ? null : buildCron(cadence, { hour, minute, weekday, dayOfMonth });

  const pastTimeError = useMemo(() => {
    if (cadence !== 'once' || !runAt) return null;
    const d = new Date(runAt);
    if (Number.isNaN(d.getTime())) return 'Choose a valid date and time.';
    return d.getTime() <= Date.now() ? 'Choose a time in the future.' : null;
  }, [cadence, runAt]);

  const preview = buildSchedulePreview(cadence, { runAt, hour, minute, weekday, dayOfMonth });

  const nameValid = name.trim().length > 0;
  const timeValid = cadence === 'once' ? Boolean(runAt) && !pastTimeError : Boolean(time);
  const monthDayValid = cadence !== 'monthly' || (Number(dayOfMonth) >= 1 && Number(dayOfMonth) <= 31);
  const canSave = nameValid && timeValid && monthDayValid && !pastTimeError;

  const handleSave = () => {
    if (!canSave) return;
    onSave?.({
      name: name.trim(),
      cron_expr: cadence === 'once' ? null : cronExpr,
      run_at: cadence === 'once' ? new Date(runAt).toISOString() : null,
    });
  };

  const renderTimeFields = () => {
    if (cadence === 'once') {
      return (
        <TextField
          fullWidth
          size="small"
          type="datetime-local"
          label="Run at"
          value={runAt}
          onChange={(e) => setRunAt(e.target.value)}
          error={Boolean(pastTimeError)}
          helperText={pastTimeError || undefined}
          inputProps={{ 'aria-label': 'Run at' }}
          InputLabelProps={{ shrink: true }}
          sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
      );
    }
    return (
      <Stack direction="row" spacing={1} alignItems="flex-start">
        <TextField
          size="small"
          type="time"
          label="Time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          inputProps={{ 'aria-label': 'Time' }}
          InputLabelProps={{ shrink: true }}
          sx={{ flex: 1, '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />
        {cadence === 'weekly' && (
          <Autocomplete
            size="small"
            options={WEEKDAYS}
            getOptionLabel={(o) => o.label}
            isOptionEqualToValue={(o, v) => o.value === v.value}
            value={WEEKDAYS.find((w) => w.value === weekday) || WEEKDAYS[1]}
            onChange={(_e, v) => v && setWeekday(v.value)}
            renderInput={(params) => (
              <TextField {...params} size="small" label="On" inputProps={{ ...params.inputProps, 'aria-label': 'Weekday' }} />
            )}
            sx={{ flex: 1, '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
          />
        )}
        {cadence === 'monthly' && (
          <TextField
            size="small"
            type="number"
            label="Day of month"
            value={dayOfMonth}
            onChange={(e) => setDayOfMonth(Number(e.target.value))}
            error={!monthDayValid}
            inputProps={{ 'aria-label': 'Day of month', min: 1, max: 31 }}
            InputLabelProps={{ shrink: true }}
            sx={{ flex: 1, '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
          />
        )}
      </Stack>
    );
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth aria-label="Schedule a plan">
      <DialogTitle sx={{ fontSize: '0.875rem', fontWeight: 700, py: 1.5 }}>
        {schedule ? 'Edit schedule' : 'Schedule a plan'}
      </DialogTitle>
      <DialogContent dividers sx={{ pt: 1.25 }}>
        {template && !schedule && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 1 }}>
            Scheduling template “{template.name}”. Scheduled runs follow the same approval and audit rules as a manual run.
          </Typography>
        )}

        <TextField
          fullWidth
          size="small"
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          inputProps={{ 'aria-label': 'Schedule name' }}
          sx={{ mb: 1.5, '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />

        <Autocomplete
          size="small"
          options={CADENCES}
          getOptionLabel={(o) => o.label}
          isOptionEqualToValue={(o, v) => o.value === v.value}
          value={CADENCES.find((c) => c.value === cadence) || CADENCES[0]}
          onChange={(_e, v) => v && setCadence(v.value)}
          renderInput={(params) => (
            <TextField {...params} size="small" label="Cadence" inputProps={{ ...params.inputProps, 'aria-label': 'Cadence' }} />
          )}
          sx={{ mb: 1.5, '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
        />

        {renderTimeFields()}

        {/* Plain-language preview (RULE_23 — outcome copy, not a cron string). */}
        <Box sx={{ mt: 1.5, p: 1, borderRadius: 1, bgcolor: 'action.hover' }} data-testid="schedule-preview">
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Preview
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
            {preview}
          </Typography>
        </Box>

        {/* Raw cron — progressive disclosure for power users only (RULE_23). */}
        <Button
          size="small"
          color="inherit"
          onClick={() => setShowCron((v) => !v)}
          endIcon={showCron ? <ExpandMoreIcon sx={{ fontSize: '0.9375rem' }} /> : <ChevronRightIcon sx={{ fontSize: '0.9375rem' }} />}
          sx={{ mt: 1, fontSize: '0.625rem', textTransform: 'none', px: 0, minWidth: 0 }}
        >
          Schedule expression
        </Button>
        <Collapse in={showCron}>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, fontSize: '0.6875rem', fontFamily: 'monospace' }}>
            {cadence === 'once' ? (runAt ? new Date(runAt).toISOString() : '—') : (cronExpr || '—')}
          </Typography>
        </Collapse>
      </DialogContent>
      <DialogActions sx={{ px: 2, py: 1 }}>
        <Button size="small" onClick={onClose} disabled={busy} sx={{ fontSize: '0.6875rem', textTransform: 'none' }}>
          Cancel
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={handleSave}
          disabled={busy || !canSave}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {busy ? 'Saving…' : 'Save schedule'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

ScheduleDialog.propTypes = {
  open: PropTypes.bool,
  schedule: PropTypes.object,
  template: PropTypes.object,
  busy: PropTypes.bool,
  onSave: PropTypes.func,
  onClose: PropTypes.func,
};
