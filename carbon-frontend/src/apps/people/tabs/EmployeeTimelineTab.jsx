// src/apps/people/tabs/EmployeeTimelineTab.jsx
// Employee governance timeline — chronological events from the backend
// (`GET people/employees/<id>/timeline/`). Read-only list.

import React, { useEffect, useState } from 'react';
import { Alert, Box, Paper, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../../auth/AuthContext';
import { fetchEmployeeTimeline } from '../../../api/people';
import LoadingSkeleton from '../../../components/Page/LoadingSkeleton';
import EmptyState from '../../../components/Page/EmptyState';
import { formatDate } from '../utils';

function renderDiff(before, after) {
  const parts = [];
  for (const key of ['basic_salary', 'org_unit_id']) {
    if (before && key in before && after && key in after) {
      parts.push(`${key}: ${before[key] ?? '—'} → ${after[key] ?? '—'}`);
    }
  }
  return parts.join(' · ');
}

export default function EmployeeTimelineTab({ entityData }) {
  const { t } = useTranslation('people');
  const { user } = useAuth();
  const employee = entityData || {};

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const loadEvents = async () => {
      if (!employee.id || !user?.token) {
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const data = await fetchEmployeeTimeline(employee.id, user.token);
        if (!cancelled) setEvents(Array.isArray(data) ? data : []);
      } catch (err) {
        if (!cancelled) setError(err?.message || t('timelineLoadError'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadEvents();
    return () => {
      cancelled = true;
    };
  }, [employee.id, user?.token, t]);

  if (loading) {
    return <LoadingSkeleton variant="detail" />;
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (events.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <EmptyState title={t('timelineEmpty')} description={t('timelineEmptyDesc')} />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Stack spacing={1.5}>
        {events.map((event) => {
          const diff = renderDiff(event.before, event.after);
          return (
            <Paper key={event.id} variant="outlined" sx={{ p: 2 }}>
              <Stack spacing={0.5}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  {String(event.event_kind).charAt(0).toUpperCase() + String(event.event_kind).slice(1)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('colEffectiveDate')}: {formatDate(event.effective_date)} ·{' '}
                  {t('colUpdatedAt')}: {formatDate(event.recorded_at)}
                </Typography>
                {event.notes && (
                  <Typography variant="body2" color="text.secondary">
                    {event.notes}
                  </Typography>
                )}
                {diff && (
                  <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>
                    {diff}
                  </Typography>
                )}
              </Stack>
            </Paper>
          );
        })}
      </Stack>
    </Box>
  );
}
