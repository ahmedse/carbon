// src/apps/my/components/RequestAttendanceDialog.jsx
// Request short-hours attendance permission (SystemDialog). Submits via
// submitAttendancePermission → POST people/me/attendance-permissions/.

import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import { submitAttendancePermission } from '../../../api/my';

const PERMISSION_TYPES = ['personal', 'medical', 'official', 'emergency'];

function mapSubmitError(t, err) {
  const detail = err?.data?.detail;
  if (typeof detail === 'string') {
    switch (detail) {
      case 'permission_type is required':
        return t('errorPermissionTypeRequired');
      case 'Invalid permission_type':
        return t('errorInvalidPermissionType');
      case 'Invalid date (expected ISO date)':
        return t('errorInvalidDate');
      case 'hours must be a positive number':
        return t('errorHoursPositive');
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

export default function RequestAttendanceDialog({ open, onClose, profile, onSubmitted }) {
  const { t } = useTranslation('my');
  const { token } = useAuth();

  const [permissionType, setPermissionType] = useState('personal');
  const [dateValue, setDateValue] = useState('');
  const [hours, setHours] = useState('2');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const firstFieldRef = useRef(null);

  useEffect(() => {
    if (open) {
      setPermissionType('personal');
      setDateValue('');
      setHours('2');
      setNotes('');
      setSubmitError(null);
      setSubmitting(false);
      const id = setTimeout(() => firstFieldRef.current?.focus(), 0);
      return () => clearTimeout(id);
    }
    return undefined;
  }, [open]);

  const canSubmit =
    Boolean(permissionType && dateValue && hours) &&
    !Number.isNaN(Number(hours)) &&
    Number(hours) > 0 &&
    !submitting;

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitAttendancePermission(token, {
        permission_type: permissionType,
        date: dateValue,
        hours: String(hours),
        notes: notes || '',
      });
      onSubmitted();
    } catch (err) {
      setSubmitError(mapSubmitError(t, err));
    } finally {
      setSubmitting(false);
    }
  }, [canSubmit, token, permissionType, dateValue, hours, notes, onSubmitted, t]);

  const managerName = profile?.manager?.full_name || profile?.manager_name;

  return (
    <SystemDialog
      open={open}
      onClose={submitting ? undefined : onClose}
      title={t('attendanceDialogTitle')}
      actions={
        <>
          <Button onClick={onClose} disabled={submitting}>
            {t('cancelButton')}
          </Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!canSubmit}
            startIcon={submitting ? <CircularProgress size={14} color="inherit" /> : null}
          >
            {t('confirmButton')}
          </Button>
        </>
      }
    >
      <Stack spacing={2}>
        {submitError && (
          <Alert severity="error" role="alert">
            {submitError}
          </Alert>
        )}
        <TextField
          select
          inputRef={firstFieldRef}
          label={t('fieldPermissionType')}
          value={permissionType}
          onChange={(e) => setPermissionType(e.target.value)}
          fullWidth
          size="small"
        >
          {PERMISSION_TYPES.map((code) => (
            <MenuItem key={code} value={code}>
              {t(`permissionType.${code}`, { defaultValue: code })}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          type="date"
          label={t('fieldPermissionDate')}
          value={dateValue}
          onChange={(e) => setDateValue(e.target.value)}
          fullWidth
          size="small"
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          type="number"
          label={t('fieldHours')}
          value={hours}
          onChange={(e) => setHours(e.target.value)}
          fullWidth
          size="small"
          inputProps={{ min: 0.25, step: 0.25 }}
        />
        <TextField
          label={t('fieldNote')}
          placeholder={t('fieldNotePlaceholder')}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          fullWidth
          size="small"
          multiline
          minRows={2}
        />
        <Box>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
            {t('approverTitle')}
          </Typography>
          <Typography variant="body2">
            {managerName
              ? t('approverManagerNamed', { name: managerName, defaultValue: managerName })
              : t('approverLineManagerWillApprove')}
          </Typography>
        </Box>
      </Stack>
    </SystemDialog>
  );
}

RequestAttendanceDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  profile: PropTypes.object,
  onSubmitted: PropTypes.func.isRequired,
};

RequestAttendanceDialog.defaultProps = {
  profile: null,
};
