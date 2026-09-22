// src/apps/my/components/NewRequestDialog.jsx
// New Request composer (SystemDialog) for the My app (Phase OF-17).
// One dialog drives every governed type: leave, loan, profile-change, and the
// payload-only memo/circular/decision types. A type selector switches the
// dynamic form (RequestFormSwitch); the approver-chain preview + confirm are
// shown before submit. Submits through apiFetch wrappers only.

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import { useTranslation } from 'react-i18next';
import SystemDialog from '../../../components/SystemDialog';
import { SearchSelect } from '../../../components/Form';
import { useAuth } from '../../../auth/AuthContext';
import { useReferenceOptions } from '../../../hooks/useReferenceOptions';
import {
  submitLeaveRequest,
  submitLoanRequest,
  submitProfileChange,
  submitGenericCorrespondence,
} from '../../../api/my';
import { fetchOrgUnits } from '../../../api/orgUnits';
import { CORR_TYPES, corrTypeLabel } from './myRequestsLabels';
import { PROFILE_CHANGE_FIELDS, isProfileChangeField } from './profileChangeAllowlist';

// ── Constants & pure helpers ───────────────────────────────────────────

/** Fallback leave-type codes when no balance rows are available. */
const LEAVE_TYPE_CODES = ['annual', 'sick', 'emergency', 'maternity', 'unpaid', 'paternity'];

/** Which field set each governed type uses (the type → field map). */
const TYPE_FIELD_GROUP = {
  leave_request: 'leave',
  loan_request: 'loan',
  profile_change: 'profile',
  internal_memo: 'generic',
  circular: 'generic',
  decision: 'generic',
};

function makeInitialForm() {
  return {
    leave_type: '',
    start_date: '',
    end_date: '',
    note: '',
    loan_type: '',
    principal: '',
    interest_rate: '',
    term_months: '',
    loan_start_date: '',
    loan_notes: '',
    title: '',
    body: '',
    changes: [{ field: '', current: '', value: '' }],
  };
}

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
      case 'loan_type is required':
        return t('errorLoanTypeRequired');
      case 'principal must be a positive number':
        return t('errorPrincipalPositive');
      case 'interest_rate must be a non-negative number':
        return t('errorInterestRate');
      case 'term_months must be a positive integer':
        return t('errorTermMonths');
      case 'Invalid start_date (expected ISO date)':
        return t('errorLoanStartDate');
      case 'title is required':
        return t('errorTitleRequired');
      case 'corr_type is required':
        return t('errorSelectRequestType');
      case 'org_unit is required':
        return t('errorOrgUnitRequired');
      case 'Submission blocked by DQ gate':
        return t('errorDqGate');
      case 'No workflow policy configured':
        return t('errorNoWorkflow');
      default:
        if (detail.startsWith('Invalid transition')) return t('errorInvalidTransition');
        if (detail.startsWith('changes must be a non-empty')) return t('errorChangesRequired');
        if (detail.startsWith('change for ')) return t('errorChangeNewRequired');
        if (detail.startsWith('Unknown corr_type')) return t('errorSelectRequestType');
        if (detail.startsWith('Unknown org_unit')) return t('submitError');
        return detail;
    }
  }
  if (err?.message === 'Request timed out' || err?.message === 'Network error') {
    return t('submitError');
  }
  return err?.message || t('submitError');
}

// ── Approver chain preview ─────────────────────────────────────────────

function ApproverChainPreview({ profile }) {
  const { t } = useTranslation('my');
  const managerName = profile?.manager?.name;

  return (
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
  );
}

ApproverChainPreview.propTypes = {
  profile: PropTypes.object,
};

ApproverChainPreview.defaultProps = {
  profile: null,
};

// ── Dynamic form (per-type field sets) ─────────────────────────────────

function RequestFormSwitch({
  requestType,
  form,
  errors,
  setField,
  leaveOptions,
  hasBalances,
  leaveDays,
  leaveEndBeforeStart,
  loanTypeOptions,
  loanTypeLoading,
  loanTypeError,
  loanTypeRetry,
  onAddChange,
  onRemoveChange,
  onUpdateChange,
}) {
  const { t, i18n } = useTranslation('my');

  switch (requestType) {
    case 'leave_request':
      return (
        <>
          <TextField
            select
            size="small"
            fullWidth
            required
            label={t('fieldLeaveType')}
            value={form.leave_type}
            onChange={(e) => setField('leave_type', e.target.value)}
            error={Boolean(errors.leave_type)}
            helperText={errors.leave_type}
          >
            {leaveOptions.map((option) => {
              const code = option.leave_type;
              const remaining = Number(option.remaining ?? 0);
              const disabled = hasBalances ? remaining <= 0 : false;
              return (
                <MenuItem key={code} value={code} disabled={disabled}>
                  {leaveTypeLabel(i18n, t, code)}
                  {hasBalances
                    ? ` — ${t('balanceRemaining', { days: option.remaining ?? '0' })}`
                    : ''}
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
            value={form.start_date}
            onChange={(e) => setField('start_date', e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            error={Boolean(errors.start_date)}
            helperText={errors.start_date}
          />
          <TextField
            size="small"
            fullWidth
            required
            type="date"
            label={t('fieldEndDate')}
            value={form.end_date}
            onChange={(e) => setField('end_date', e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            error={Boolean(errors.end_date)}
            helperText={errors.end_date}
          />
          {leaveEndBeforeStart && <Alert severity="error">{t('errorEndBeforeStart')}</Alert>}
          <TextField
            size="small"
            fullWidth
            label={t('fieldDays')}
            value={leaveDays == null ? '' : String(Math.max(1, leaveDays))}
            helperText={
              leaveDays == null
                ? t('daysSummaryLabel')
                : t('daysSummaryCount', { count: Math.max(1, leaveDays) })
            }
            slotProps={{ input: { readOnly: true } }}
          />
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={2}
            label={t('fieldNote')}
            placeholder={t('fieldNotePlaceholder')}
            value={form.note}
            onChange={(e) => setField('note', e.target.value)}
          />
        </>
      );

    case 'loan_request':
      return (
        <>
          <SearchSelect
            label={t('fieldLoanType')}
            options={loanTypeOptions}
            value={form.loan_type}
            onChange={(v) => setField('loan_type', v?.value ?? '')}
            loading={loanTypeLoading}
            error={errors.loan_type || loanTypeError}
            helperText={errors.loan_type || undefined}
            onRetry={loanTypeRetry}
            required
            clearable={false}
            placeholder={t('fieldLoanTypePlaceholder')}
          />
          <TextField
            size="small"
            fullWidth
            required
            type="number"
            label={t('fieldPrincipal')}
            value={form.principal}
            onChange={(e) => setField('principal', e.target.value)}
            slotProps={{ htmlInput: { min: 0, step: '0.01' } }}
            error={Boolean(errors.principal)}
            helperText={errors.principal}
          />
          <TextField
            size="small"
            fullWidth
            type="number"
            label={t('fieldInterestRate')}
            value={form.interest_rate}
            onChange={(e) => setField('interest_rate', e.target.value)}
            slotProps={{ htmlInput: { min: 0, step: '0.01' } }}
            error={Boolean(errors.interest_rate)}
            helperText={errors.interest_rate}
          />
          <TextField
            size="small"
            fullWidth
            required
            type="number"
            label={t('fieldTermMonths')}
            value={form.term_months}
            onChange={(e) => setField('term_months', e.target.value)}
            slotProps={{ htmlInput: { min: 1, step: 1 } }}
            error={Boolean(errors.term_months)}
            helperText={errors.term_months}
          />
          <TextField
            size="small"
            fullWidth
            required
            type="date"
            label={t('fieldLoanStartDate')}
            value={form.loan_start_date}
            onChange={(e) => setField('loan_start_date', e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            error={Boolean(errors.loan_start_date)}
            helperText={errors.loan_start_date}
          />
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={2}
            label={t('fieldLoanNotes')}
            placeholder={t('fieldLoanNotesPlaceholder')}
            value={form.loan_notes}
            onChange={(e) => setField('loan_notes', e.target.value)}
          />
        </>
      );

    case 'profile_change': {
      const selectedFields = new Set(
        form.changes.map((c) => c.field).filter(Boolean),
      );
      const fieldOptions = PROFILE_CHANGE_FIELDS.map((code) => ({
        value: code,
        label: t(`profileField.${code}`, { defaultValue: code }),
      }));
      return (
        <>
          <Typography variant="body2" color="text.secondary">
            {t('profileChangeHint')}
          </Typography>
          {form.changes.map((change, index) => {
            const optionsForRow = fieldOptions.filter(
              (o) => o.value === change.field || !selectedFields.has(o.value),
            );
            const isDate = change.field === 'date_of_birth';
            return (
              <Stack key={index} direction="row" spacing={0.5} alignItems="flex-start">
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <SearchSelect
                    label={t('fieldChangeField')}
                    options={optionsForRow}
                    value={change.field}
                    onChange={(v) => onUpdateChange(index, { field: v?.value ?? '' })}
                    required
                    clearable={false}
                    error={errors[`changes.${index}.field`]}
                    helperText={errors[`changes.${index}.field`]}
                    placeholder={t('fieldChangeFieldPlaceholder')}
                  />
                </Box>
                <TextField
                  size="small"
                  fullWidth
                  label={t('fieldChangeCurrent')}
                  value={change.current}
                  onChange={(e) => onUpdateChange(index, { current: e.target.value })}
                />
                <TextField
                  size="small"
                  fullWidth
                  required
                  type={isDate ? 'date' : 'text'}
                  label={t('fieldChangeNew')}
                  value={change.value}
                  onChange={(e) => onUpdateChange(index, { value: e.target.value })}
                  error={Boolean(errors[`changes.${index}.value`])}
                  helperText={errors[`changes.${index}.value`]}
                  slotProps={isDate ? { inputLabel: { shrink: true } } : undefined}
                />
                <IconButton
                  size="small"
                  onClick={() => onRemoveChange(index)}
                  disabled={form.changes.length === 1}
                  aria-label={t('removeChangeField')}
                  sx={{ mt: 0.5 }}
                >
                  <RemoveCircleOutlineIcon fontSize="small" />
                </IconButton>
              </Stack>
            );
          })}
          {errors.changes && <Alert severity="error">{errors.changes}</Alert>}
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={onAddChange}
            disabled={selectedFields.size >= PROFILE_CHANGE_FIELDS.length}
          >
            {t('addChangeField')}
          </Button>
        </>
      );
    }

    case 'internal_memo':
    case 'circular':
    case 'decision':
      return (
        <>
          <TextField
            size="small"
            fullWidth
            required
            label={t('fieldTitle')}
            placeholder={t('fieldTitlePlaceholder')}
            value={form.title}
            onChange={(e) => setField('title', e.target.value)}
            error={Boolean(errors.title)}
            helperText={errors.title}
          />
          <TextField
            size="small"
            fullWidth
            required
            multiline
            minRows={4}
            label={t('fieldBody')}
            placeholder={t('fieldBodyPlaceholder')}
            value={form.body}
            onChange={(e) => setField('body', e.target.value)}
            error={Boolean(errors.body)}
            helperText={errors.body}
          />
        </>
      );

    default:
      return null;
  }
}

RequestFormSwitch.propTypes = {
  requestType: PropTypes.string.isRequired,
  form: PropTypes.object.isRequired,
  errors: PropTypes.object.isRequired,
  setField: PropTypes.func.isRequired,
  leaveOptions: PropTypes.array.isRequired,
  hasBalances: PropTypes.bool.isRequired,
  leaveDays: PropTypes.number,
  leaveEndBeforeStart: PropTypes.bool.isRequired,
  loanTypeOptions: PropTypes.array,
  loanTypeLoading: PropTypes.bool,
  loanTypeError: PropTypes.string,
  loanTypeRetry: PropTypes.func,
  onAddChange: PropTypes.func.isRequired,
  onRemoveChange: PropTypes.func.isRequired,
  onUpdateChange: PropTypes.func.isRequired,
};

RequestFormSwitch.defaultProps = {
  leaveDays: null,
  loanTypeOptions: [],
  loanTypeLoading: false,
  loanTypeError: null,
  loanTypeRetry: undefined,
};

// ── Main dialog ────────────────────────────────────────────────────────

export default function NewRequestDialog({ open, onClose, profile, balances, onSubmitted }) {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const loanTypeRef = useReferenceOptions('loan_type');

  const [requestType, setRequestType] = useState('');
  const [form, setForm] = useState(makeInitialForm);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [orgUnits, setOrgUnits] = useState([]);
  const [selectedOrgUnit, setSelectedOrgUnit] = useState('');

  const firstFieldRef = useRef(null);

  // F20: payload-only types need an org_unit. Employees carry one on their
  // profile; profile-less users (e.g. admins) must pick one in the dialog.
  const needsOrgUnit =
    ['internal_memo', 'circular', 'decision'].includes(requestType) && !profile?.org_unit?.id;

  // Memoized type → field-group lookup (the module constant is read once).
  const fieldGroup = useMemo(() => TYPE_FIELD_GROUP[requestType] || null, [requestType]);

  const hasBalances = Array.isArray(balances) && balances.length > 0;
  const leaveOptions = useMemo(
    () => (hasBalances ? balances : LEAVE_TYPE_CODES.map((code) => ({ leave_type: code }))),
    [hasBalances, balances]
  );

  const leaveEndBeforeStart = useMemo(() => {
    if (requestType !== 'leave_request') return false;
    if (!form.start_date || !form.end_date) return false;
    const start = parseISODate(form.start_date);
    const end = parseISODate(form.end_date);
    return Boolean(start && end && end < start);
  }, [requestType, form.start_date, form.end_date]);

  const leaveDays = useMemo(() => {
    if (requestType !== 'leave_request') return null;
    if (!form.start_date || !form.end_date) return null;
    return countWorkingDays(form.start_date, form.end_date);
  }, [requestType, form.start_date, form.end_date]);

  const setField = useCallback((key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  }, []);

  const addChange = useCallback(() => {
    setForm((prev) => ({
      ...prev,
      changes: [...prev.changes, { field: '', current: '', value: '' }],
    }));
  }, []);

  const removeChange = useCallback((index) => {
    setForm((prev) => ({ ...prev, changes: prev.changes.filter((_, i) => i !== index) }));
  }, []);

  const updateChange = useCallback((index, partial) => {
    setForm((prev) => ({
      ...prev,
      changes: prev.changes.map((change, i) => (i === index ? { ...change, ...partial } : change)),
    }));
  }, []);

  // Reset the form each time the dialog opens.
  useEffect(() => {
    if (open) {
      setRequestType('');
      setForm(makeInitialForm());
      setErrors({});
      setSubmitError(null);
      setSubmitting(false);
      setSelectedOrgUnit('');
      const id = setTimeout(() => firstFieldRef.current?.focus(), 0);
      return () => clearTimeout(id);
    }
    return undefined;
  }, [open]);

  // Load org units once when a profile-less user selects a payload-only type.
  useEffect(() => {
    if (!open || !needsOrgUnit || orgUnits.length > 0) return undefined;
    let active = true;
    fetchOrgUnits(token)
      .then((list) => {
        if (active) setOrgUnits(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (active) setOrgUnits([]);
      });
    return () => {
      active = false;
    };
  }, [open, needsOrgUnit, orgUnits.length, token]);

  const validate = useCallback(() => {
    const next = {};
    switch (requestType) {
      case 'leave_request':
        if (!form.leave_type) next.leave_type = t('errorSelectType');
        if (!form.start_date || !form.end_date) next.start_date = t('errorSelectDates');
        else if (leaveEndBeforeStart) next.end_date = t('errorEndBeforeStart');
        break;
      case 'loan_request':
        if (!form.loan_type.trim()) next.loan_type = t('errorLoanTypeRequired');
        if (
          !form.principal ||
          Number.isNaN(Number(form.principal)) ||
          Number(form.principal) <= 0
        ) {
          next.principal = t('errorPrincipalPositive');
        }
        if (
          form.interest_rate !== '' &&
          (Number.isNaN(Number(form.interest_rate)) || Number(form.interest_rate) < 0)
        ) {
          next.interest_rate = t('errorInterestRate');
        }
        if (
          !form.term_months ||
          !Number.isInteger(Number(form.term_months)) ||
          Number(form.term_months) <= 0
        ) {
          next.term_months = t('errorTermMonths');
        }
        if (!form.loan_start_date) next.loan_start_date = t('errorLoanStartDate');
        break;
      case 'profile_change': {
        const filled = form.changes.filter((c) => c.field.trim() || c.value.trim());
        if (filled.length === 0) {
          next.changes = t('errorChangesRequired');
        } else {
          form.changes.forEach((c, i) => {
            if (!c.field.trim() && c.value.trim()) {
              next[`changes.${i}.field`] = t('errorChangeFieldRequired');
            } else if (c.field.trim() && !isProfileChangeField(c.field.trim())) {
              next[`changes.${i}.field`] = t('errorChangeFieldNotAllowed');
            }
            if (c.field.trim() && !c.value.trim()) {
              next[`changes.${i}.value`] = t('errorChangeNewRequired');
            }
          });
        }
        break;
      }
      case 'internal_memo':
      case 'circular':
      case 'decision':
        if (!form.title.trim()) next.title = t('errorTitleRequired');
        if (!form.body.trim()) next.body = t('errorBodyRequired');
        if (needsOrgUnit && !selectedOrgUnit) next.org_unit = t('errorOrgUnitRequired');
        break;
      default:
        next.requestType = t('errorSelectRequestType');
        break;
    }
    return next;
  }, [requestType, form, leaveEndBeforeStart, needsOrgUnit, selectedOrgUnit, t]);

  const handleSubmit = useCallback(async () => {
    if (!requestType) {
      setErrors({ requestType: t('errorSelectRequestType') });
      return;
    }
    const nextErrors = validate();
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setErrors({});
    try {
      switch (requestType) {
        case 'leave_request': {
          const payload = {
            leave_type: form.leave_type,
            start_date: form.start_date,
            end_date: form.end_date,
            days: String(Math.max(1, leaveDays ?? 1)),
          };
          if (form.note.trim()) payload.note = form.note.trim();
          await submitLeaveRequest(token, payload);
          break;
        }
        case 'loan_request': {
          const payload = {
            loan_type: form.loan_type.trim(),
            principal: form.principal,
            interest_rate: form.interest_rate === '' ? '0' : form.interest_rate,
            term_months: Number(form.term_months),
            start_date: form.loan_start_date,
          };
          if (form.loan_notes.trim()) payload.notes = form.loan_notes.trim();
          await submitLoanRequest(token, payload);
          break;
        }
        case 'profile_change': {
          const changes = {};
          form.changes.forEach((c) => {
            if (!c.field.trim() || !c.value.trim()) return;
            const entry = { to: c.value.trim() };
            if (c.current.trim()) entry.from = c.current.trim();
            changes[c.field.trim()] = entry;
          });
          await submitProfileChange(token, { changes });
          break;
        }
        default: {
          const payload = {
            corr_type: requestType,
            title: form.title.trim(),
            payload: { body: form.body.trim() },
          };
          if (profile?.org_unit?.id) payload.org_unit = profile.org_unit.id;
          else if (selectedOrgUnit) payload.org_unit = selectedOrgUnit;
          await submitGenericCorrespondence(token, payload);
          break;
        }
      }
      onSubmitted(requestType);
    } catch (err) {
      setSubmitError(mapSubmitError(t, err));
    } finally {
      setSubmitting(false);
    }
  }, [requestType, form, leaveDays, profile, selectedOrgUnit, token, t, validate, onSubmitted]);

  const canSubmit = Boolean(requestType) && !submitting;

  return (
    <SystemDialog
      open={open}
      title={t('newRequestTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('cancelButton')}
      width={560}
      height={680}
      actions={
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={!canSubmit}
          startIcon={submitting ? <CircularProgress size={14} color="inherit" /> : null}
        >
          {t('confirmButton')}
        </Button>
      }
    >
      <Stack spacing={1.5}>
        {submitError && (
          <Alert severity="error" onClose={() => setSubmitError(null)} aria-live="polite">
            {submitError}
          </Alert>
        )}

        <TextField
          select
          size="small"
          fullWidth
          required
          label={t('fieldRequestType')}
          value={requestType}
          onChange={(e) => {
            setRequestType(e.target.value);
            setErrors({});
            setSubmitError(null);
          }}
          inputRef={firstFieldRef}
          error={Boolean(errors.requestType)}
          helperText={errors.requestType}
          aria-required="true"
        >
          {CORR_TYPES.map((code) => (
            <MenuItem key={code} value={code}>
              {corrTypeLabel(t, code)}
            </MenuItem>
          ))}
        </TextField>

        <RequestFormSwitch
          requestType={requestType}
          form={form}
          errors={errors}
          setField={setField}
          leaveOptions={leaveOptions}
          hasBalances={hasBalances}
          leaveDays={leaveDays}
          leaveEndBeforeStart={leaveEndBeforeStart}
          loanTypeOptions={loanTypeRef.options}
          loanTypeLoading={loanTypeRef.loading}
          loanTypeError={loanTypeRef.error}
          loanTypeRetry={loanTypeRef.refetch}
          onAddChange={addChange}
          onRemoveChange={removeChange}
          onUpdateChange={updateChange}
        />

        {needsOrgUnit && (
          <TextField
            select
            size="small"
            fullWidth
            required
            label={t('fieldOrgUnit')}
            value={selectedOrgUnit}
            onChange={(e) => {
              setSelectedOrgUnit(e.target.value);
              setErrors((prev) => ({ ...prev, org_unit: undefined }));
            }}
            error={Boolean(errors.org_unit)}
            helperText={errors.org_unit}
          >
            {orgUnits.map((unit) => (
              <MenuItem key={unit.id} value={String(unit.id)}>
                {unit.name || unit.code || String(unit.id)}
              </MenuItem>
            ))}
          </TextField>
        )}

        {fieldGroup && <ApproverChainPreview profile={profile} />}
      </Stack>
    </SystemDialog>
  );
}

NewRequestDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  profile: PropTypes.object,
  balances: PropTypes.array,
  onSubmitted: PropTypes.func.isRequired,
};

NewRequestDialog.defaultProps = {
  profile: null,
  balances: [],
};
