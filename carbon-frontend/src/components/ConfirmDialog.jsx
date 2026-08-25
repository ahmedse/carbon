// src/components/ConfirmDialog.jsx
// Standard confirmation dialog built on SystemDialog. Replaces window.confirm
// with a consistent, accessible, system-styled dialog (RULE 11 / RULE 12).

import React from 'react';
import { Button, Typography, Box } from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import SystemDialog from './SystemDialog';

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  destructive = false,
  onConfirm,
  onCancel,
  ...props
}) {
  const { t } = useTranslation('common');
  const theme = useTheme();
  const resolvedTitle = title ?? t('confirm');
  const resolvedConfirmLabel = confirmLabel ?? t('confirm');
  const resolvedCancelLabel = cancelLabel ?? t('cancel');

  return (
    <SystemDialog
      open={open}
      title={resolvedTitle}
      onClose={onCancel}
      onCancel={onCancel}
      showCancel={false}
      cancelLabel={resolvedCancelLabel}
      width={440}
      height={260}
      minWidth={380}
      minHeight={220}
      {...props}
      actions={
        <>
          <Button onClick={onCancel} color='inherit'>
            {resolvedCancelLabel}
          </Button>
          <Button
            variant='contained'
            color={destructive ? 'error' : 'primary'}
            onClick={onConfirm}
            autoFocus
          >
            {resolvedConfirmLabel}
          </Button>
        </>
      }
    >
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', mt: 1 }}>
        <WarningAmberIcon
          sx={{
            color: destructive ? theme.palette.error.main : theme.palette.warning.main,
            mt: 0.25,
          }}
        />
        <Typography variant='body2' color='text.secondary' sx={{ whiteSpace: 'pre-line' }}>
          {message}
        </Typography>
      </Box>
    </SystemDialog>
  );
}
