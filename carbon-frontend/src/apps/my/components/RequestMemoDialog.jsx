// Edit payload-only memo / circular / decision while sent_back (SystemDialog).

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
import { useAuth } from '../../../auth/AuthContext';
import { editCorrespondence } from '../../../api/my';

export default function RequestMemoDialog({
  open,
  onClose,
  onSubmitted,
  correspondenceId,
  initialTitle,
  initialPayload,
  corrTypeCode,
}) {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    if (!open) return;
    setTitle(initialTitle || '');
    const payload = initialPayload && typeof initialPayload === 'object'
      ? initialPayload
      : {};
    setBody(payload.body || '');
    setSubmitError(null);
    setSubmitting(false);
  }, [open, initialTitle, initialPayload]);

  const canSubmit = Boolean(title.trim() && body.trim()) && !submitting;

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await editCorrespondence(token, correspondenceId, {
        title: title.trim(),
        payload: { body: body.trim() },
      });
      onSubmitted();
    } catch (err) {
      setSubmitError(err?.data?.detail || err?.message || t('submitError'));
    } finally {
      setSubmitting(false);
    }
  }, [canSubmit, token, correspondenceId, title, body, onSubmitted, t]);

  const titleKey =
    corrTypeCode === 'circular'
      ? 'editCircularDialogTitle'
      : corrTypeCode === 'decision'
        ? 'editDecisionDialogTitle'
        : 'editMemoDialogTitle';

  return (
    <SystemDialog
      open={open}
      title={t(titleKey)}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('cancelButton')}
      width={560}
      height={480}
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
        <TextField
          size="small"
          fullWidth
          required
          label={t('fieldTitle')}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <TextField
          size="small"
          fullWidth
          required
          multiline
          minRows={6}
          label={t('fieldBody')}
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
      </Stack>
    </SystemDialog>
  );
}

RequestMemoDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSubmitted: PropTypes.func.isRequired,
  correspondenceId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  initialTitle: PropTypes.string,
  initialPayload: PropTypes.object,
  corrTypeCode: PropTypes.string,
};

RequestMemoDialog.defaultProps = {
  initialTitle: '',
  initialPayload: null,
  corrTypeCode: 'internal_memo',
};
