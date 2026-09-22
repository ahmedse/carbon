// src/apps/my/components/RequestLeaveDialog.jsx
// Request Leave dialog (SystemDialog — the platform modal primitive, per
// .ai-toolkit/shared/frontend-ready.md "Form uses SystemDialog, never raw
// Drawer/Dialog"). Collects leave_type, start/end dates, computes working days
// (Mon–Fri, min 1), optional note, and a static approver-chain preview. Submits
// via submitLeaveRequest (apiFetch); on success calls onSubmitted (parent closes
// + refetches). Surfaces backend 400 `detail` messages inline (Alert role="alert").
// All strings via useTranslation('my'); all colors via theme tokens.

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import SystemDialog from '../../../components/SystemDialog';
import { useAuth } from '../../../auth/AuthContext';
import { editCorrespondence, submitLeaveRequest } from '../../../api/my';

// ── Pure helpers ──────────────────────────────────────────────────────

/** Parse a YYYY-MM-DD date into a local Date (no timezone shift). */
function parseISODate(value) {
  if (!value) return null;
  const [y, m, d] = String(value).slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return null;
  const date = new Date(y, m - 1, d);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Count weekdays (Mon–Fri) inclusive between two ISO dates; null if invalid. */
function countWorkingDays(startValue, endValue) {
  const start = parseISODate(startValue);
  const end = parseISODate(endValue);
  if (!start || !end || end < start) return null;
  let count = 0;
  const cursor = new Date(start);
  while (cursor <= end) {
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) count += 1;
    cursor.setDate(cursor.getDate() + 1);
  }
  return count;
}

/** Localized label for a leave-type code, falling back to the raw code. */
function leaveTypeLabel(i18n, t, code) {
  if (!code) return t('profileNotAvailable');
  const key = `leaveType.${code}`;
  return t(key, { defaultValue: code });
}

/** Map a backend/network error to a localized, human-readable message. */
function mapSubmitError(t, err) {
  const detail = err?.data?.detail;
  if (typeof detail === 'string') {
    switch (detail) {
      case 'Insufficient leave balance': {
        const remaining = err?.data?.remaining;
        return remaining != null
          ? `${t('insufficientBalance')} — ${t('balanceRemaining', { days: remaining })}`
          : t('insufficientBalance');
      }
      case 'Overlaps existing leave request':
        return t('errorOverlap');
      case 'days must be a positive number':
        return t('errorDaysPositive');
      case 'Invalid start_date/end_date (expected ISO date)':
        return t('errorInvalidDate');
      case 'end_date must be on or after start_date':
        return t('errorEndBeforeStart');
      case 'leave_type is required':
        return t('errorLeaveTypeRequired');
      case 'Submission blocked by DQ gate':
        return t('errorDqGate');
      case 'No workflow policy configured':
        return t('errorNoWorkflow');
      default:
        if (detail.startsWith('Invalid transition')) return t('errorInvalidTransition');
        return detail;
    }
  }
  if (err?.message === 'Request timed out' || err?.message === 'Network error') {
    return t('submitError');
  }
  return err?.message || t('submitError');
}

// ── Component ─────────────────────────────────────────────────────────

export default function RequestLeaveDialog({
  open,
  onClose,
  balances,
  profile,
  onSubmitted,
  mode,
  correspondenceId,
  initialPayload,
}) {
  const { t, i18n } = useTranslation('my');
  const { token } = useAuth();
  const isEdit = mode === 'edit';

  const [leaveType, setLeaveType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const firstFieldRef = useRef(null);

  const options = useMemo(() => (Array.isArray(balances) ? balances : []), [balances]);

  const hasDates = Boolean(startDate && endDate);
  const endBeforeStart = useMemo(() => {
    if (!hasDates) return false;
    const start = parseISODate(startDate);
    const end = parseISODate(endDate);
    return Boolean(start && end && end < start);
  }, [startDate, endDate, hasDates]);

  const days = useMemo(
    () => (hasDates ? countWorkingDays(startDate, endDate) : null),
    [startDate, endDate, hasDates]
  );
  const displayDays = days == null ? 0 : Math.max(1, days);

  const canSubmit = Boolean(leaveType && startDate && endDate) && !endBeforeStart && !submitting;

  // Prefill (edit) or reset (create) each time the dialog opens.
  useEffect(() => {
    if (open) {
      if (isEdit && initialPayload && typeof initialPayload === 'object') {
        setLeaveType(initialPayload.leave_type || '');
        setStartDate(String(initialPayload.start_date || '').slice(0, 10));
        setEndDate(String(initialPayload.end_date || '').slice(0, 10));
        setNote(initialPayload.note || '');
      } else {
        setLeaveType('');
        setStartDate('');
        setEndDate('');
        setNote('');
      }
      setSubmitError(null);
      setSubmitting(false);
      const id = setTimeout(() => firstFieldRef.current?.focus(), 0);
      return () => clearTimeout(id);
    }
    return undefined;
  }, [open, isEdit, initialPayload]);

  const handleSubmit = useCallback(async () => {
    if (!leaveType) {
      setSubmitError(t('errorSelectType'));
      return;
    }
    if (!startDate || !endDate) {
      setSubmitError(t('errorSelectDates'));
      return;
    }
    if (endBeforeStart) {
      setSubmitError(t('errorEndBeforeStart'));
      return;
    }

    const payload = {
      leave_type: leaveType,
      start_date: startDate,
      end_date: endDate,
      days: String(displayDays),
    };
    const trimmedNote = note.trim();
    if (trimmedNote) payload.note = trimmedNote;

    setSubmitting(true);
    setSubmitError(null);
    try {
      if (isEdit) {
        if (correspondenceId == null) {
          setSubmitError(t('submitError'));
          return;
        }
        await editCorrespondence(token, correspondenceId, { payload });
      } else {
        await submitLeaveRequest(token, payload);
      }
      onSubmitted();
    } catch (err) {
      setSubmitError(mapSubmitError(t, err));
    } finally {
      setSubmitting(false);
    }
  }, [
    leaveType,
    startDate,
    endDate,
    endBeforeStart,
    displayDays,
    note,
    token,
    t,
    onSubmitted,
    isEdit,
    correspondenceId,
  ]);

  const managerName = profile?.manager?.name;

  return (
    <SystemDialog
      open={open}
      title={isEdit ? t('editLeaveDialogTitle') : t('dialogTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('cancelButton')}
      width={520}
      height={580}
      actions={
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={!canSubmit}
          startIcon={submitting ? <CircularProgress size={14} color="inherit" /> : null}
        >
          {isEdit ? t('saveEditsButton') : t('confirmButton')}
        </Button>
      }
    >
      <Stack spacing={1.5}>
        {submitError && (
          <Alert severity="error" onClose={() => setSubmitError(null)}>
            {submitError}
          </Alert>
        )}

        <TextField
          select
          size="small"
          fullWidth
          required
          label={t('fieldLeaveType')}
          value={leaveType}
          onChange={(e) => setLeaveType(e.target.value)}
          inputRef={firstFieldRef}
          aria-required="true"
        >
          {options.map((balance) => {
            const remaining = Number(balance.remaining ?? 0);
            const disabled = remaining <= 0;
            return (
              <MenuItem key={balance.leave_type} value={balance.leave_type} disabled={disabled}>
                {leaveTypeLabel(i18n, t, balance.leave_type)}
                {' — '}
                {t('balanceRemaining', { days: balance.remaining ?? '0' })}
              </MenuItem>
            );
          })}
        </TextField>

        <TextField
          size="small"
          fullWidth
          required
          type="date"
          label={t('fieldStartDate')}
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          aria-required="true"
        />

        <TextField
          size="small"
          fullWidth
          required
          type="date"
          label={t('fieldEndDate')}
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          aria-required="true"
        />

        {endBeforeStart && <Alert severity="error">{t('errorEndBeforeStart')}</Alert>}

        <TextField
          size="small"
          fullWidth
          label={t('fieldDays')}
          value={days == null ? '' : String(displayDays)}
          helperText={days == null ? t('daysSummaryLabel') : t('daysSummaryCount', { count: displayDays })}
          slotProps={{ input: { readOnly: true } }}
        />

        <TextField
          size="small"
          fullWidth
          multiline
          minRows={3}
          label={t('fieldNote')}
          placeholder={t('fieldNotePlaceholder')}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />

        {/* Approver chain preview (create only — edit keeps existing chain) */}
        {!isEdit ? (
          <Box>
            <Typography variant="overline" color="text.secondary" sx={{ display: 'block' }}>
              {t('approverTitle')}
            </Typography>
            <Typography variant="body2">
              {managerName
                ? `${t('approverManagerWillApprove')} — ${managerName}`
                : t('approverLineManagerWillApprove')}
            </Typography>
          </Box>
        ) : (
          <Alert severity="info">{t('editLeaveHint')}</Alert>
        )}
      </Stack>
    </SystemDialog>
  );
}

RequestLeaveDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  balances: PropTypes.array,
  profile: PropTypes.object,
  onSubmitted: PropTypes.func.isRequired,
  mode: PropTypes.oneOf(['create', 'edit']),
  correspondenceId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  initialPayload: PropTypes.object,
};

RequestLeaveDialog.defaultProps = {
  balances: [],
  profile: null,
  mode: 'create',
  correspondenceId: null,
  initialPayload: null,
};
