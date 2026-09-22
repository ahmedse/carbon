// src/apps/my/components/RequestLoanDialog.jsx
// Create or edit (sent_back) loan request via SystemDialog.
// Create → POST people/me/loan/; edit → POST correspondence/{id}/edit/.

import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Button,
  CircularProgress,
  Stack,
  TextField,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import SystemDialog from '../../../components/SystemDialog';
import { SearchSelect } from '../../../components/Form';
import { useAuth } from '../../../auth/AuthContext';
import { useReferenceOptions } from '../../../hooks/useReferenceOptions';
import { editCorrespondence, submitLoanRequest } from '../../../api/my';

function mapError(t, err) {
  const detail = err?.data?.detail;
  if (typeof detail === 'string') {
    if (detail.startsWith('Unknown loan_type')) return t('errorLoanTypeRequired');
    if (detail.includes('principal')) return t('errorPrincipalPositive');
    if (detail.includes('interest_rate')) return t('errorInterestNonNegative');
    if (detail.includes('term_months')) return t('errorTermMonthsPositive');
    if (detail.includes('start_date')) return t('errorInvalidDate');
    if (detail.startsWith('Invalid transition')) return t('errorInvalidTransition');
    if (detail.includes('DQ')) return t('errorDqGate');
    if (detail.includes('workflow')) return t('errorNoWorkflow');
    return detail;
  }
  return err?.message || t('submitError');
}

export default function RequestLoanDialog({
  open,
  onClose,
  onSubmitted,
  mode,
  correspondenceId,
  initialPayload,
}) {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const loanTypeRef = useReferenceOptions('loan_type');
  const isEdit = mode === 'edit';

  const [loanType, setLoanType] = useState('');
  const [principal, setPrincipal] = useState('');
  const [interestRate, setInterestRate] = useState('0');
  const [termMonths, setTermMonths] = useState('');
  const [startDate, setStartDate] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    if (!open) return undefined;
    if (isEdit && initialPayload && typeof initialPayload === 'object') {
      setLoanType(initialPayload.loan_type || '');
      setPrincipal(String(initialPayload.principal ?? ''));
      setInterestRate(String(initialPayload.interest_rate ?? '0'));
      setTermMonths(String(initialPayload.term_months ?? ''));
      setStartDate(String(initialPayload.start_date || '').slice(0, 10));
      setNotes(initialPayload.notes || '');
    } else {
      setLoanType('');
      setPrincipal('');
      setInterestRate('0');
      setTermMonths('');
      setStartDate('');
      setNotes('');
    }
    setSubmitError(null);
    setSubmitting(false);
    return undefined;
  }, [open, isEdit, initialPayload]);

  const canSubmit =
    Boolean(loanType && principal && termMonths && startDate) &&
    Number(principal) > 0 &&
    Number(termMonths) > 0 &&
    !submitting &&
    !loanTypeRef.loading;

  const handleSubmit = useCallback(async () => {
    const payload = {
      loan_type: loanType,
      principal: String(principal),
      interest_rate: interestRate.trim() === '' ? '0' : String(interestRate),
      term_months: Number(termMonths),
      start_date: startDate,
    };
    if (notes.trim()) payload.notes = notes.trim();

    setSubmitting(true);
    setSubmitError(null);
    try {
      if (isEdit) {
        await editCorrespondence(token, correspondenceId, { payload });
      } else {
        await submitLoanRequest(token, payload);
      }
      onSubmitted();
    } catch (err) {
      setSubmitError(mapError(t, err));
    } finally {
      setSubmitting(false);
    }
  }, [
    loanType, principal, interestRate, termMonths, startDate, notes,
    token, t, onSubmitted, isEdit, correspondenceId,
  ]);

  return (
    <SystemDialog
      open={open}
      title={isEdit ? t('editLoanDialogTitle') : t('newRequestLoanTitle', { defaultValue: t('dialogTitle') })}
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
        {submitError ? (
          <Alert severity="error" onClose={() => setSubmitError(null)}>{submitError}</Alert>
        ) : null}
        {isEdit ? <Alert severity="info">{t('editLeaveHint')}</Alert> : null}
        <SearchSelect
          label={t('fieldLoanType')}
          options={loanTypeRef.options || []}
          value={loanType}
          onChange={(v) => setLoanType(v?.value ?? '')}
          loading={loanTypeRef.loading}
          error={loanTypeRef.error}
          onRetry={loanTypeRef.refetch}
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
          value={principal}
          onChange={(e) => setPrincipal(e.target.value)}
          slotProps={{ htmlInput: { min: 0, step: '0.01' } }}
        />
        <TextField
          size="small"
          fullWidth
          type="number"
          label={t('fieldInterestRate')}
          value={interestRate}
          onChange={(e) => setInterestRate(e.target.value)}
          slotProps={{ htmlInput: { min: 0, step: '0.01' } }}
        />
        <TextField
          size="small"
          fullWidth
          required
          type="number"
          label={t('fieldTermMonths')}
          value={termMonths}
          onChange={(e) => setTermMonths(e.target.value)}
          slotProps={{ htmlInput: { min: 1, step: 1 } }}
        />
        <TextField
          size="small"
          fullWidth
          required
          type="date"
          label={t('fieldLoanStartDate')}
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          fullWidth
          multiline
          minRows={2}
          label={t('fieldLoanNotes')}
          placeholder={t('fieldLoanNotesPlaceholder')}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </Stack>
    </SystemDialog>
  );
}

RequestLoanDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSubmitted: PropTypes.func.isRequired,
  mode: PropTypes.oneOf(['create', 'edit']),
  correspondenceId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  initialPayload: PropTypes.object,
};

RequestLoanDialog.defaultProps = {
  mode: 'create',
  correspondenceId: null,
  initialPayload: null,
};
