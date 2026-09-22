// src/apps/people/tabs/EmployeeEosiTab.jsx
// EOSI (end-of-service indemnity) provision — A17 / DESIGN P5.
// Lazy GET people/employees/<id>/eosi/?as_of= — value + lineage; 409 = no rule.

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import CalculateIcon from '@mui/icons-material/Calculate';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../../auth/AuthContext';
import { fetchEmployeeEosi } from '../../../api/people';
import EmptyState from '../../../components/Page/EmptyState';
import { formatAmount, formatDate } from '../utils';

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function inputRows(inputs) {
  if (!inputs || typeof inputs !== 'object') return [];
  return Object.entries(inputs).map(([key, value]) => ({
    key,
    value: value == null ? '—' : String(value),
  }));
}

export default function EmployeeEosiTab({ entityData }) {
  const { t } = useTranslation('people');
  const { token } = useAuth();
  const employeeId = entityData?.empId ?? entityData?.id;

  const [asOf, setAsOf] = useState(todayIso);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [conflict, setConflict] = useState(null);

  const load = useCallback(async () => {
    if (!employeeId || !token) return;
    setLoading(true);
    setError(null);
    setConflict(null);
    try {
      const data = await fetchEmployeeEosi(employeeId, token, { asOf: asOf || undefined });
      setResult(data);
    } catch (err) {
      setResult(null);
      if (err?.status === 409) {
        setConflict(err.message || t('eosiNoRule'));
      } else {
        setError(err?.message || t('eosiLoadError'));
      }
    } finally {
      setLoading(false);
    }
  }, [employeeId, token, asOf, t]);

  useEffect(() => {
    load();
  }, [load]);

  if (!employeeId) {
    return <EmptyState icon={CalculateIcon} title={t('eosiEmpty')} />;
  }

  const lineage = result?.lineage || {};
  const rows = inputRows(lineage.inputs);

  return (
    <Box sx={{ p: 2, maxWidth: 720 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        alignItems={{ xs: 'stretch', sm: 'flex-end' }}
        sx={{ mb: 2 }}
      >
        <TextField
          label={t('eosiAsOf')}
          type="date"
          size="small"
          value={asOf}
          onChange={(e) => setAsOf(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ minWidth: 180 }}
        />
        <Button
          size="small"
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={load}
          disabled={loading}
        >
          {t('eosiRecalculate')}
        </Button>
      </Stack>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={28} />
        </Box>
      )}

      {!loading && conflict && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {conflict}
        </Alert>
      )}

      {!loading && error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {!loading && !conflict && !error && result && (
        <Stack spacing={2}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography
              variant="caption"
              sx={{
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.07em',
                color: 'text.secondary',
                display: 'block',
                mb: 0.5,
              }}
            >
              {t('eosiProvision')}
            </Typography>
            <Typography
              variant="h4"
              sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}
              dir="ltr"
            >
              {formatAmount(result.value)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('eosiAsOfLabel', { date: formatDate(result.as_of) || result.as_of || '—' })}
            </Typography>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography
              variant="caption"
              sx={{
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.07em',
                color: 'text.secondary',
                display: 'block',
                mb: 1,
              }}
            >
              {t('eosiLineage')}
            </Typography>
            <Stack spacing={0.75} sx={{ mb: rows.length ? 1.5 : 0 }}>
              <Typography variant="body2">
                <Box component="span" sx={{ color: 'text.secondary' }}>{t('eosiRuleId')}: </Box>
                <Box component="span" dir="ltr">{lineage.rule_id || '—'}</Box>
              </Typography>
              <Typography variant="body2">
                <Box component="span" sx={{ color: 'text.secondary' }}>{t('eosiRuleVersion')}: </Box>
                <Box component="span" dir="ltr">{lineage.rule_version || '—'}</Box>
              </Typography>
            </Stack>
            {rows.length > 0 && (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>{t('eosiInput')}</TableCell>
                      <TableCell align="right">{t('eosiInputValue')}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {rows.map((row) => (
                      <TableRow key={row.key}>
                        <TableCell sx={{ textTransform: 'capitalize' }}>
                          {row.key.replace(/_/g, ' ')}
                        </TableCell>
                        <TableCell align="right" dir="ltr" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                          {row.value}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>
        </Stack>
      )}

      {!loading && !conflict && !error && !result && (
        <EmptyState icon={CalculateIcon} title={t('eosiEmpty')} />
      )}
    </Box>
  );
}
