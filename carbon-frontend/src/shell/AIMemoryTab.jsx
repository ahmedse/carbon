// src/shell/AIMemoryTab.jsx
// Phase 23-B — Episodic memory tab: events/milestones the assistant recorded
// while working. Self-fetching sibling of AIUsageTab — reads
// /carbon-api/ai/memory/episodes/ through the workspace api module
// (RULE_10: apiFetch only; RULE_8: theme tokens only).
//
// Response contract (Phase 23-A backend):
//   { count, results: [{ id, event_type, summary, details,
//     caused_by_episode_id, relevance_score, occurred_at, learned_at,
//     visibility }] }
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { listEpisodes } from '../api/aiWorkspace';

dayjs.extend(utc);
dayjs.extend(timezone);

const PROJECT_TIMEZONE = 'Africa/Cairo';

/** Humanize an ISO timestamp in the project timezone as "MMM D, YYYY · HH:mm". */
function formatWhen(iso) {
  if (!iso) return '—';
  return dayjs.tz(iso, PROJECT_TIMEZONE).format('MMM D, YYYY · HH:mm');
}

/** Render episode.details (JSON object | string | null) compactly. */
function formatDetails(details) {
  if (details == null) return '';
  if (typeof details === 'string') return details;
  try {
    return JSON.stringify(details);
  } catch {
    return String(details);
  }
}

function AIMemoryTab() {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();

  const [eventType, setEventType] = useState('');
  const [episodes, setEpisodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listEpisodes(token, {
        ...(eventType ? { event_type: eventType } : {}),
        limit: 100,
      });
      setEpisodes(Array.isArray(data?.results) ? data.results : []);
    } catch (err) {
      setError(err.message || 'Could not load memory');
      notifyFromError(err, 'Could not load memory');
    } finally {
      setLoading(false);
    }
  }, [token, eventType, notifyFromError]);

  useEffect(() => {
    load();
  }, [load]);

  // Distinct event types seen in the loaded rows (filter source, client-side
  // is enough here — the list is bounded at 100 and types are low-cardinality).
  const eventTypes = useMemo(
    () => [...new Set(episodes.map((e) => e.event_type).filter(Boolean))].sort(),
    [episodes],
  );

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      {/* Toolbar */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={600} sx={{ flex: 1 }}>
          Memory
        </Typography>
        {eventTypes.length > 1 && (
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="memory-event-type-label">Event type</InputLabel>
            <Select
              labelId="memory-event-type-label"
              id="memory-event-type"
              label="Event type"
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              sx={{ fontSize: '0.8125rem' }}
            >
              <MenuItem value="" sx={{ fontSize: '0.8125rem' }}>
                All types
              </MenuItem>
              {eventTypes.map((t) => (
                <MenuItem key={t} value={t} sx={{ fontSize: '0.8125rem' }}>
                  {t}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        <Button size="small" startIcon={<RefreshIcon />} onClick={load} variant="outlined">
          Refresh
        </Button>
      </Stack>

      {/* States */}
      {loading && (
        <Typography variant="caption" color="text.secondary">
          Loading…
        </Typography>
      )}

      {!loading && error && (
        <Stack spacing={1} alignItems="flex-start">
          <Typography variant="caption" color="error.main">{error}</Typography>
          <Button size="small" variant="outlined" onClick={load}>Retry</Button>
        </Stack>
      )}

      {!loading && !error && episodes.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            No events recorded yet.
          </Typography>
          <Typography variant="caption" color="text.disabled">
            Milestones from your conversations will appear here.
          </Typography>
        </Box>
      )}

      {!loading && !error && episodes.length > 0 && (
        <Stack spacing={1}>
          {episodes.map((ep) => (
            <Paper key={ep.id} variant="outlined" sx={{ p: 1.25 }}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
                <Chip
                  size="small"
                  label={ep.event_type || 'event'}
                  variant="outlined"
                  color={ep.event_type === 'error' ? 'error' : 'info'}
                  sx={{ fontSize: '0.65rem', height: 20 }}
                />
                <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
                  {formatWhen(ep.occurred_at)}
                </Typography>
                {ep.relevance_score != null && (
                  <Typography variant="caption" color="text.disabled" noWrap>
                    relevance {(Number(ep.relevance_score) * 100).toFixed(0)}%
                  </Typography>
                )}
              </Stack>
              <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
                {ep.summary || '—'}
              </Typography>
              {formatDetails(ep.details) && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 0.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                >
                  {formatDetails(ep.details)}
                </Typography>
              )}
              <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
                Recorded {formatWhen(ep.learned_at)}
              </Typography>
            </Paper>
          ))}
        </Stack>
      )}
    </Box>
  );
}

export default AIMemoryTab;
