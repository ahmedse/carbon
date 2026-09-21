// src/pages/admin/ai/control/PlatformBudgetPanel.jsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { shellLabel } from '../../../../i18n/shellLabels';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { useNotification } from '../../../../components/NotificationProvider';
import { getBudgetControl, patchBudgetControl } from '../../../../api/aiControlPlane';
import BudgetUsagePanel from '../BudgetUsagePanel';
import EngineSettingsPanel from '../EngineSettingsPanel';
import ControlHub from './ControlHub';
import RolesMatrixPanel from './RolesMatrixPanel';

function BudgetEditor() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.platform.spendTitle'));
  const { token } = useAuth();
  const { notify } = useNotification();
  const [spend, setSpend] = useState(null);
  const [value, setValue] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getBudgetControl(token);
      setSpend(data?.spend || null);
      const override = data?.containment?.daily_budget_usd;
      setValue(override == null ? '' : String(override));
    } catch {
      setSpend(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onSave = async () => {
    setSaving(true);
    try {
      const parsed = value.trim() === '' ? null : Number(value);
      await patchBudgetControl(token, parsed);
      notify({ message: t('control.platform.budgetSaved'), type: 'success' });
      await load();
    } catch (err) {
      notify({
        message: err?.detail || err?.message || t('control.platform.saveFailed'),
        type: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <CircularProgress size={24} />
      </PageContainer>
    );
  }

  const spent = Number(spend?.spent_today_usd || 0).toFixed(2);
  const budget = Number(spend?.budget_usd || 0).toFixed(2);

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Typography variant="h5" fontWeight={700}>
          {t('control.platform.spendTitle')}
        </Typography>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="body2">
                {t('control.platform.todaySpend', { spent, budget })}
              </Typography>
              {spend?.budget_exceeded && (
                <Chip size="small" color="error" label={t('control.platform.exceeded')} />
              )}
              {spend?.override_active && (
                <Chip size="small" variant="outlined" label={t('control.platform.overrideActive')} />
              )}
            </Stack>
            <Stack direction="row" spacing={1}>
              <TextField
                size="small"
                label={t('control.platform.budgetOverride')}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                helperText={t('control.platform.budgetOverrideHint')}
              />
              <Button variant="contained" onClick={onSave} disabled={saving}>
                {t('control.platform.save')}
              </Button>
            </Stack>
          </Stack>
        </Paper>
        <BudgetUsagePanel />
      </Stack>
    </PageContainer>
  );
}

export default function PlatformHubPage() {
  const { t } = useTranslation('shell');
  const label = (english) => shellLabel(t, english);
  const tabs = useMemo(
    () => [
      { id: 'spend', label: label('Spend'), element: <BudgetEditor /> },
      { id: 'engine', label: label('Engine'), element: <EngineSettingsPanel /> },
      { id: 'roles', label: label('Roles'), element: <RolesMatrixPanel /> },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );
  return (
    <ControlHub
      title={label('Platform')}
      defaultTab="spend"
      tabs={tabs}
    />
  );
}
