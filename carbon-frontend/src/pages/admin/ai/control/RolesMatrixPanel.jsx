// src/pages/admin/ai/control/RolesMatrixPanel.jsx
// Platform → Roles: CBAC capability matrix (ADR-0036 Phase 7).
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Link,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { fetchCapabilityMatrix } from '../../../../api/accessControl';

export default function RolesMatrixPanel() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.rolesMatrix.title'));
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const body = await fetchCapabilityMatrix(token);
      setData(body);
    } catch (err) {
      setData(null);
      setError(err?.detail || err?.message || 'Failed to load capability matrix');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const aiDomain = useMemo(() => {
    const domains = Array.isArray(data?.domains) ? data.domains : [];
    return (
      domains.find((d) => d.domain === 'ai') ||
      domains.find((d) => String(d.domain).toLowerCase().includes('ai'))
    );
  }, [data]);

  const aiKeys = useMemo(() => {
    if (!aiDomain) return [];
    return (aiDomain.capabilities || []).map((c) => c.key);
  }, [aiDomain]);

  const groups = useMemo(() => {
    const matrix = Array.isArray(data?.matrix) ? data.matrix : [];
    return matrix.filter((g) => {
      const caps = g.capabilities || [];
      return caps.some((c) => aiKeys.includes(c.key) || String(c.key).startsWith('ai:'));
    });
  }, [data, aiKeys]);

  const hasCap = (group, key) =>
    (group.capabilities || []).some((c) => c.key === key);

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h5" fontWeight={700}>
            {t('control.rolesMatrix.heading')}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <Button
              size="small"
              component={RouterLink}
              to="/admin/access"
            >
              Assign users
            </Button>
            <Button size="small" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
              {t('control.rolesMatrix.refresh')}
            </Button>
          </Stack>
        </Stack>
        <Typography variant="body2" color="text.secondary">
          {t('control.rolesMatrix.subtitle')}
        </Typography>

        {loading ? (
          <CircularProgress size={24} />
        ) : error ? (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography color="error">{error}</Typography>
          </Paper>
        ) : !aiKeys.length ? (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {t('control.rolesMatrix.empty')}
            </Typography>
          </Paper>
        ) : (
          <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t('control.rolesMatrix.colGroup')}</TableCell>
                  {aiKeys.map((key) => (
                    <TableCell key={key} sx={{ whiteSpace: 'nowrap' }}>
                      <Typography variant="caption">{key.replace(/^ai:/, '')}</Typography>
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {groups.map((g) => (
                  <TableRow key={g.group}>
                    <TableCell>
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <Typography variant="body2">{g.group}</Typography>
                        {g.is_wildcard ? (
                          <Chip size="small" label="*" variant="outlined" />
                        ) : null}
                      </Stack>
                    </TableCell>
                    {aiKeys.map((key) => (
                      <TableCell key={`${g.group}-${key}`} align="center">
                        {hasCap(g, key) ? (
                          <Box
                            component="span"
                            sx={{ color: 'success.main', fontWeight: 700 }}
                          >
                            •
                          </Box>
                        ) : (
                          <Typography variant="caption" color="text.disabled">
                            —
                          </Typography>
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        <Typography variant="body2">
          Full access admin:{' '}
          <Link component={RouterLink} to="/admin/access">
            /admin/access
          </Link>
        </Typography>
      </Stack>
    </PageContainer>
  );
}
