// src/pages/catalog/GovernancePage.jsx
// Governance: Read-only audit log of governance events
import React, { useEffect, useState, useCallback } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, Table, TableHead, TableRow, TableCell, TableBody,
  CircularProgress, Alert, Chip, Paper, Button, Link as MuiLink,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import RefreshIcon from '@mui/icons-material/Refresh';
import AssignmentIcon from '@mui/icons-material/Assignment';
import { fetchGovernanceEvents } from '../../api/catalog';

function summarizeChange(before, after) {
  const b = before && typeof before === 'object' ? before : {};
  const a = after && typeof after === 'object' ? after : {};
  const keys = [...new Set([...Object.keys(b), ...Object.keys(a)])];
  if (keys.length === 0) return '—';
  const parts = keys.slice(0, 4).map((k) => {
    const from = b[k] == null || b[k] === '' ? '—' : String(b[k]);
    const to = a[k] == null || a[k] === '' ? '—' : String(a[k]);
    return `${k}: ${from} → ${to}`;
  });
  return parts.join('; ') + (keys.length > 4 ? '…' : '');
}

export default function GovernancePage() {
  useDocumentTitle("Audit Log");
  const { t } = useTranslation('catalog');
  const { token } = useAuth();
  const { notify } = useNotification();

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadEvents = useCallback(async ({ announce = false } = {}) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchGovernanceEvents(token);
      setEvents(Array.isArray(data) ? data : data?.results || []);
      if (announce) {
        notify({ message: t('eventsLoaded'), type: 'success' });
      }
    } catch (err) {
      const msg = err.message || t('governanceLoadError');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify, t]);

  useEffect(() => {
    loadEvents({ announce: false });
  }, [loadEvents]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <AssignmentIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h5" fontWeight={700}>{t('governanceLog')}</Typography>
            <Typography variant="body2" color="text.secondary">{t('governanceSubtitle')}</Typography>
          </Box>
        </Box>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => loadEvents({ announce: true })}>
          {t('refresh')}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper>
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: 'action.hover' }}>
              <TableCell fontWeight={600}>{t('eventType')}</TableCell>
              <TableCell fontWeight={600}>{t('asset')}</TableCell>
              <TableCell fontWeight={600}>{t('details')}</TableCell>
              <TableCell fontWeight={600}>{t('date')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">{t('noGovernanceEvents')}</Typography>
                </TableCell>
              </TableRow>
            ) : (
              events.map((event) => {
                const eventType = event.action || event.entity_type || '—';
                const assetId = event.asset;
                const assetLabel = assetId
                  ? t('assetNumber', { id: assetId })
                  : t('entityNumber', {
                    entity: event.entity_type || t('entity'),
                    id: event.entity_id || '?',
                  });
                const details = summarizeChange(event.before, event.after);
                const when = event.timestamp
                  ? new Date(event.timestamp).toLocaleString()
                  : '—';
                return (
                  <TableRow key={event.id} hover>
                    <TableCell>
                      <Chip label={eventType} size="small" color="primary" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      {assetId ? (
                        <MuiLink
                          component={RouterLink}
                          to={`/catalog/assets/${assetId}`}
                          underline="hover"
                        >
                          {assetLabel}
                        </MuiLink>
                      ) : (
                        assetLabel
                      )}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 360 }}>
                      <Typography variant="caption" sx={{ whiteSpace: 'pre-wrap' }}>{details}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">{when}</Typography>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
