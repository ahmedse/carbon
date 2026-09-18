// src/pages/admin/ai/control/PlatformBudgetPanel.jsx
import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
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
  useDocumentTitle('Platform Spend');
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
      notify({ message: 'Budget override saved', type: 'success' });
      await load();
    } catch (err) {
      notify({ message: err?.detail || err?.message || 'Save failed', type: 'error' });
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

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Typography variant="h5" fontWeight={700}>
          Spend & caps
        </Typography>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="body2">
                Today: ${Number(spend?.spent_today_usd || 0).toFixed(2)} / $
                {Number(spend?.budget_usd || 0).toFixed(2)}
              </Typography>
              {spend?.budget_exceeded && <Chip size="small" color="error" label="Exceeded" />}
              {spend?.override_active && (
                <Chip size="small" variant="outlined" label="Override active" />
              )}
            </Stack>
            <Stack direction="row" spacing={1}>
              <TextField
                size="small"
                label="Daily budget USD override"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                helperText="Empty clears override (uses env default)"
              />
              <Button variant="contained" onClick={onSave} disabled={saving}>
                Save
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
  return (
    <ControlHub
      title="Platform"
      defaultTab="spend"
      tabs={[
        { id: 'spend', label: 'Spend', element: <BudgetEditor /> },
        { id: 'engine', label: 'Engine', element: <EngineSettingsPanel /> },
        { id: 'roles', label: 'Roles', element: <RolesMatrixPanel /> },
      ]}
    />
  );
}
