// src/apps/my/components/RequestProfileChangeDialog.jsx
// Edit profile-change payload while sent_back (SystemDialog).
// Does not write Employee — only correspondence payload.changes.

import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Button,
  CircularProgress,
  IconButton,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useTranslation } from 'react-i18next';
import SystemDialog from '../../../components/SystemDialog';
import { SearchSelect } from '../../../components/Form';
import { useAuth } from '../../../auth/AuthContext';
import { editCorrespondence } from '../../../api/my';
import { PROFILE_CHANGE_FIELDS } from './profileChangeAllowlist';

function rowsFromPayload(payload) {
  const changes = payload?.changes;
  if (!changes || typeof changes !== 'object') {
    return [{ field: '', from: '', to: '' }];
  }
  const rows = Object.entries(changes).map(([field, change]) => ({
    field,
    from: change && typeof change === 'object' ? String(change.from ?? '') : '',
    to: change && typeof change === 'object' ? String(change.to ?? '') : '',
  }));
  return rows.length ? rows : [{ field: '', from: '', to: '' }];
}

export default function RequestProfileChangeDialog({
  open,
  onClose,
  onSubmitted,
  correspondenceId,
  initialPayload,
}) {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const [rows, setRows] = useState([{ field: '', from: '', to: '' }]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    if (!open) return;
    setRows(rowsFromPayload(initialPayload));
    setSubmitError(null);
    setSubmitting(false);
  }, [open, initialPayload]);

  const fieldOptions = PROFILE_CHANGE_FIELDS.map((code) => ({
    value: code,
    label: t(`profileField.${code}`, { defaultValue: code }),
  }));

  const selected = new Set(rows.map((r) => r.field).filter(Boolean));

  const canSubmit =
    rows.some((r) => r.field && String(r.to).trim() !== '') && !submitting;

  const handleSubmit = useCallback(async () => {
    const changes = {};
    rows.forEach((r) => {
      if (!r.field || String(r.to).trim() === '') return;
      const entry = { to: r.to };
      if (String(r.from).trim() !== '') entry.from = r.from;
      changes[r.field] = entry;
    });
    if (!Object.keys(changes).length) {
      setSubmitError(t('errorChangesRequired'));
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await editCorrespondence(token, correspondenceId, {
        payload: { changes },
      });
      onSubmitted();
    } catch (err) {
      setSubmitError(err?.data?.detail || err?.message || t('submitError'));
    } finally {
      setSubmitting(false);
    }
  }, [rows, token, correspondenceId, onSubmitted, t]);

  return (
    <SystemDialog
      open={open}
      title={t('editProfileDialogTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('cancelButton')}
      width={560}
      height={560}
      actions={
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={!canSubmit}
          startIcon={submitting ? <CircularProgress size={14} color="inherit" /> : null}
        >
          {t('saveEditsButton')}
        </Button>
      }
    >
      <Stack spacing={1.5}>
        {submitError ? (
          <Alert severity="error" onClose={() => setSubmitError(null)}>{submitError}</Alert>
        ) : null}
        <Alert severity="info">{t('editLeaveHint')}</Alert>
        {rows.map((row, index) => (
          <Stack key={`pc-row-${index}`} spacing={1} direction={{ xs: 'column', sm: 'row' }} alignItems="flex-start">
            <SearchSelect
              label={t('fieldChangeField')}
              options={fieldOptions.filter(
                (o) => o.value === row.field || !selected.has(o.value),
              )}
              value={row.field}
              onChange={(v) => {
                const next = [...rows];
                next[index] = { ...next[index], field: v?.value ?? '' };
                setRows(next);
              }}
              required
              clearable={false}
              sx={{ minWidth: 160, flex: 1 }}
            />
            <TextField
              size="small"
              label={t('fieldChangeCurrent')}
              value={row.from}
              onChange={(e) => {
                const next = [...rows];
                next[index] = { ...next[index], from: e.target.value };
                setRows(next);
              }}
              sx={{ flex: 1 }}
            />
            <TextField
              size="small"
              required
              label={t('fieldChangeNew')}
              value={row.to}
              onChange={(e) => {
                const next = [...rows];
                next[index] = { ...next[index], to: e.target.value };
                setRows(next);
              }}
              sx={{ flex: 1 }}
            />
            <IconButton
              size="small"
              aria-label={t('removeChangeField')}
              disabled={rows.length <= 1}
              onClick={() => setRows(rows.filter((_, i) => i !== index))}
            >
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Stack>
        ))}
        <Button
          size="small"
          startIcon={<AddIcon />}
          disabled={selected.size >= PROFILE_CHANGE_FIELDS.length}
          onClick={() => setRows([...rows, { field: '', from: '', to: '' }])}
          sx={{ alignSelf: 'flex-start', textTransform: 'none' }}
        >
          {t('addChangeField')}
        </Button>
        <Typography variant="caption" color="text.secondary">
          {t('profileChangeEditNote', {
            defaultValue: 'Changes apply to your profile only after the request is approved again.',
          })}
        </Typography>
      </Stack>
    </SystemDialog>
  );
}

RequestProfileChangeDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSubmitted: PropTypes.func.isRequired,
  correspondenceId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  initialPayload: PropTypes.object,
};

RequestProfileChangeDialog.defaultProps = {
  initialPayload: null,
};
