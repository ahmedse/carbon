// src/apps/people/RevealAmount.jsx
// Tier-2 progressive disclosure for compensation. Compensation is masked by
// default and only revealed on demand through the audited compensation endpoint
// (`POST /people/employees/:id/compensation/`). Every reveal is a governance
// event on the server — never rely on CSS hiding for sensitive amounts.

import React, { useState } from 'react';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import LockIcon from '@mui/icons-material/Lock';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth/AuthContext';
import { useCompensationAccess } from './useCompensationAccess';
import { revealEmployeeCompensation } from '../../api/people';
import { formatAmount } from './utils';

const MASKED = '\u2022\u2022\u2022\u2022\u2022\u2022';

export default function RevealAmount({ employeeId, size = 'small' }) {
  const { t } = useTranslation('people');
  const { token } = useAuth();
  const { canViewCompensation } = useCompensationAccess();
  const [value, setValue] = useState(null);
  const [revealing, setRevealing] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!canViewCompensation) {
    return (
      <Tooltip title={t('compensationRestricted')}>
        <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, color: 'text.disabled' }}>
          <LockIcon fontSize="inherit" sx={{ fontSize: 14 }} />
          <Typography variant="body2" sx={{ fontSize: '0.7rem' }}>
            {t('restrictedLabel')}
          </Typography>
        </Box>
      </Tooltip>
    );
  }

  if (value != null) {
    return (
      <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
        <Typography
          variant="body2"
          sx={{ fontSize: '0.72rem', fontVariantNumeric: 'tabular-nums', color: 'text.primary' }}
        >
          {formatAmount(value)}
        </Typography>
        <Tooltip title={t('hideAmount')}>
          <IconButton size={size} onClick={() => setValue(null)} sx={{ color: 'text.secondary' }}>
            <VisibilityOffIcon fontSize="inherit" sx={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>
      </Box>
    );
  }

  const reveal = async () => {
    if (revealing) return;
    setRevealing(true);
    setFailed(false);
    try {
      const data = await revealEmployeeCompensation(employeeId, token);
      setValue(data?.basic_salary ?? null);
    } catch {
      setFailed(true);
    } finally {
      setRevealing(false);
    }
  };

  return (
    <Tooltip title={failed ? t('revealFailed') : t('revealAmount')}>
      <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
        <Typography
          variant="body2"
          sx={{ fontSize: '0.72rem', letterSpacing: 1, color: 'text.secondary' }}
        >
          {MASKED}
        </Typography>
        <IconButton size={size} onClick={reveal} disabled={revealing} sx={{ color: 'primary.main' }}>
          <VisibilityIcon fontSize="inherit" sx={{ fontSize: 14 }} />
        </IconButton>
      </Box>
    </Tooltip>
  );
}
