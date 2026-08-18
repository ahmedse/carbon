// src/shell/AILearntTab.jsx
// Phase 23-B — Learnt facts tab: durable facts the assistant picked up from
// past conversations, each with confidence + provenance and a per-fact
// Forget action (confirm dialog → hard delete + cascade, audited server-side).
// Self-fetching sibling of AIUsageTab — reads /carbon-api/ai/memory/facts/ and
// deletes /carbon-api/ai/memory/facts/{id}/ through the workspace api module
// (RULE_10: apiFetch only; RULE_8: theme tokens only; RULE_23: outcome copy).
//
// Response contract (Phase 23-A backend):
//   { count, results: [{ id, category, content, confidence,
//     provenance: { source, created_at, last_used }, use_count, visibility,
//     valid_from, valid_to }] }
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { forgetFact, listFacts } from '../api/aiWorkspace';

dayjs.extend(utc);
dayjs.extend(timezone);

const PROJECT_TIMEZONE = 'Africa/Cairo';

/** Humanize an ISO timestamp in the project timezone as "MMM D, YYYY". */
function formatDate(iso) {
  if (!iso) return '—';
  return dayjs.tz(iso, PROJECT_TIMEZONE).format('MMM D, YYYY');
}

/** User-facing source label — outcomes, never internals (RULE_23). */
function sourceLabel(source) {
  if (!source) return 'from a past conversation';
  if (source.startsWith('user_feedback:')) return 'from your feedback';
  if (source.startsWith('superseded:')) return 'built on an earlier fact';
  if (source.startsWith('conversation:')) return 'from a past conversation';
  return 'from a past conversation';
}

function AILearntTab() {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [category, setCategory] = useState('');
  const [facts, setFacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [forgetTarget, setForgetTarget] = useState(null);
  const [forgetting, setForgetting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFacts(token, {
        ...(category ? { category } : {}),
        limit: 100,
      });
      setFacts(Array.isArray(data?.results) ? data.results : []);
    } catch (err) {
      setError(err.message || 'Could not load learnt facts');
      notifyFromError(err, 'Could not load learnt facts');
    } finally {
      setLoading(false);
    }
  }, [token, category, notifyFromError]);

  useEffect(() => {
    load();
  }, [load]);

  // Distinct categories in the loaded rows (filter source, client-side is
  // enough — the list is bounded at 100 and categories are low-cardinality).
  const categories = useMemo(
    () => [...new Set(facts.map((f) => f.category).filter(Boolean))].sort(),
    [facts],
  );

  const handleForget = useCallback(async () => {
    if (!forgetTarget) return;
    const target = forgetTarget;
    setForgetting(true);
    try {
      await forgetFact(token, target.id);
      setFacts((prev) => prev.filter((f) => f.id !== target.id));
      setForgetTarget(null);
      notify({ message: 'Forgotten — removed from what I remember.', type: 'success' });
    } catch (err) {
      notifyFromError(err, 'Could not forget this fact');
    } finally {
      setForgetting(false);
    }
  }, [forgetTarget, token, notify, notifyFromError]);

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      {/* Toolbar */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={600} sx={{ flex: 1 }}>
          Learnt facts
        </Typography>
        {categories.length > 1 && (
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="learnt-category-label">Category</InputLabel>
            <Select
              labelId="learnt-category-label"
              id="learnt-category"
              label="Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              sx={{ fontSize: '0.8125rem' }}
            >
              <MenuItem value="" sx={{ fontSize: '0.8125rem' }}>
                All categories
              </MenuItem>
              {categories.map((c) => (
                <MenuItem key={c} value={c} sx={{ fontSize: '0.8125rem' }}>
                  {c}
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

      {!loading && !error && facts.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Nothing learnt yet.
          </Typography>
          <Typography variant="caption" color="text.disabled">
            Facts I pick up from your conversations will appear here — and you
            can forget any of them.
          </Typography>
        </Box>
      )}

      {!loading && !error && facts.length > 0 && (
        <Stack spacing={1}>
          {facts.map((fact) => {
            const confidence = Math.max(0, Math.min(100, Math.round((Number(fact.confidence) || 0) * 100)));
            return (
              <Paper key={fact.id} variant="outlined" sx={{ p: 1.25 }}>
                <Stack direction="row" alignItems="flex-start" spacing={1}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
                      <Chip
                        size="small"
                        label={fact.category || 'fact'}
                        variant="outlined"
                        color="primary"
                        sx={{ fontSize: '0.65rem', height: 20 }}
                      />
                      <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
                        {sourceLabel(fact.provenance?.source)} · {formatDate(fact.provenance?.created_at)}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
                      {fact.content}
                    </Typography>
                    <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 0.75 }}>
                      <LinearProgress
                        variant="determinate"
                        value={confidence}
                        sx={{ flex: 1, maxWidth: 120, height: 4, borderRadius: 1 }}
                        aria-label={`Confidence for ${fact.content}`}
                      />
                      <Typography variant="caption" color="text.secondary" noWrap>
                        {confidence}% confident
                      </Typography>
                      {Number(fact.use_count) > 0 && (
                        <Typography variant="caption" color="text.disabled" noWrap>
                          · used {Number(fact.use_count)}×
                        </Typography>
                      )}
                    </Stack>
                  </Box>
                  <Tooltip title="Forget this fact">
                    <Button
                      size="small"
                      variant="text"
                      color="error"
                      startIcon={<DeleteOutlineIcon sx={{ fontSize: 15 }} />}
                      onClick={() => setForgetTarget(fact)}
                      sx={{ fontSize: '0.7rem', minWidth: 0 }}
                    >
                      Forget
                    </Button>
                  </Tooltip>
                </Stack>
              </Paper>
            );
          })}
        </Stack>
      )}

      {/* Forget confirm — outcome copy, no internals (RULE_23). */}
      <Dialog open={Boolean(forgetTarget)} onClose={() => setForgetTarget(null)}>
        <DialogTitle>Forget this fact?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            I will stop using “{forgetTarget?.content}” and remove anything I
            built on top of it. This cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button size="small" onClick={() => setForgetTarget(null)} disabled={forgetting}>
            Cancel
          </Button>
          <Button size="small" color="error" variant="contained" onClick={handleForget} disabled={forgetting}>
            {forgetting ? 'Forgetting…' : 'Forget'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default AILearntTab;
