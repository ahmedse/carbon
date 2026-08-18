// src/shell/AIRelationshipTab.jsx
// Phase 23-B — Relationship tab: what the assistant remembers about this
// user, computed per request (never persisted server-side). This is the
// "empathy surface": every claim is paired with a plain-language "why" and a
// forget affordance, so the user always knows where the signal came from and
// how to remove it. Empty state is explicit — never a scary inference.
//
// Self-fetching sibling of AIUsageTab — reads /carbon-api/ai/memory/relationship/
// through the workspace api module (RULE_10: apiFetch only; RULE_8: theme
// tokens only; RULE_23: outcome copy — no model/endpoint names).
//
// Response contract (Phase 23-A backend):
//   { memory_enabled, memory: { fact_count, episode_count,
//     top_categories: [{ category, count }], avg_confidence, total_uses },
//     usage: {...}, profile: {...}, computed_at }
import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { getRelationship } from '../api/aiWorkspace';
import { formatTokens } from './AIUsageTab';

/** A single claim: title + plain-language "why" + an action affordance. */
function ClaimCard({ title, why, action }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.25 }}>
      <Stack direction="row" alignItems="flex-start" spacing={1}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8125rem' }}>
            {title}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
            {why}
          </Typography>
        </Box>
        {action}
      </Stack>
    </Paper>
  );
}

/**
 * @param {object} props
 * @param {() => void} [props.onShowFacts] - open the Learnt facts tab
 * @param {() => void} [props.onShowEpisodes] - open the Memory (episodes) tab
 * @param {() => void} [props.onShowUsage] - open the Usage tab
 */
function AIRelationshipTab({ onShowFacts, onShowEpisodes, onShowUsage }) {
  const { token } = useAuth();
  const { notifyFromError } = useNotification();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rel = await getRelationship(token);
      setData(rel || null);
    } catch (err) {
      setError(err.message || 'Could not load relationship');
      notifyFromError(err, 'Could not load relationship');
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError]);

  useEffect(() => {
    load();
  }, [load]);

  const memory = data?.memory || null;
  const usage = data?.usage || null;
  const memoryEnabled = data?.memory_enabled !== false;
  const hasMemory = memory && (Number(memory.fact_count) > 0 || Number(memory.episode_count) > 0);

  const topCategories = Array.isArray(memory?.top_categories) ? memory.top_categories : [];
  const confidence = memory?.avg_confidence != null ? Math.round(Number(memory.avg_confidence) * 100) : null;

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      {/* Toolbar */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={600} sx={{ flex: 1 }}>
          Relationship
        </Typography>
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

      {!loading && !error && data && !hasMemory && (
        <Box sx={{ textAlign: 'center', py: 6, maxWidth: 380, mx: 'auto' }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Nothing stored yet.
          </Typography>
          <Typography variant="caption" color="text.disabled" sx={{ display: 'block' }}>
            I don't keep anything from our chats on my own. When you confirm
            something I've learned — a preference, a fact, a milestone — it
            shows up here, with the reason and a way to forget it.
          </Typography>
        </Box>
      )}

      {!loading && !error && data && hasMemory && (
        <Stack spacing={1.5}>
          {!memoryEnabled && (
            <Paper variant="outlined" sx={{ p: 1.25, borderColor: 'warning.main' }}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Chip size="small" label="Memory off" color="warning" variant="outlined" sx={{ fontSize: '0.65rem', height: 20 }} />
                <Typography variant="caption" color="text.secondary">
                  Long-term memory is turned off, so nothing new will be stored.
                  What's already here stays visible until you forget it.
                </Typography>
              </Stack>
            </Paper>
          )}

          {/* Learnt facts claim */}
          <ClaimCard
            title={`${Number(memory.fact_count) || 0} ${Number(memory.fact_count) === 1 ? 'fact' : 'facts'} I've learned about how you work`}
            why="Each one comes from a past conversation where you confirmed or taught it — and every one has a source you can inspect."
            action={
              <Button size="small" variant="outlined" color="primary" onClick={onShowFacts} sx={{ fontSize: '0.7rem', minWidth: 0, whiteSpace: 'nowrap' }}>
                Review &amp; forget
              </Button>
            }
          />

          {/* Episodes claim */}
          <ClaimCard
            title={`${Number(memory.episode_count) || 0} ${Number(memory.episode_count) === 1 ? 'event' : 'events'} I remember from our work`}
            why="Milestones and moments recorded while we worked together — you can review or remove any of them."
            action={
              <Button size="small" variant="outlined" color="primary" onClick={onShowEpisodes} sx={{ fontSize: '0.7rem', minWidth: 0, whiteSpace: 'nowrap' }}>
                Review
              </Button>
            }
          />

          {/* Confidence / trust claim */}
          {confidence != null && (
            <ClaimCard
              title={`I'm about ${confidence}% sure of what I've learned`}
              why="Confidence grows when the same thing shows up across conversations; it drops when you correct me."
              action={
                <Button size="small" variant="outlined" color="primary" onClick={onShowFacts} sx={{ fontSize: '0.7rem', minWidth: 0, whiteSpace: 'nowrap' }}>
                  Review &amp; forget
                </Button>
              }
            />
          )}

          {/* Topics claim */}
          {topCategories.length > 0 && (
            <Paper variant="outlined" sx={{ p: 1.25 }}>
              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8125rem' }}>
                Topics I keep in mind
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                The categories you've taught me most about — each is just a
                group of the facts above.
              </Typography>
              <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                {topCategories.map((tc) => (
                  <Chip
                    key={tc.category}
                    size="small"
                    label={`${tc.category} · ${Number(tc.count) || 0}`}
                    variant="outlined"
                    color="primary"
                    sx={{ fontSize: '0.65rem', height: 20 }}
                  />
                ))}
                <Button size="small" variant="text" color="primary" onClick={onShowFacts} sx={{ fontSize: '0.7rem', minWidth: 0 }}>
                  Forget any
                </Button>
              </Stack>
            </Paper>
          )}

          {/* Usage claim — no forget affordance: usage is not memory. */}
          {usage && (Number(usage.total_tokens) > 0 || Number(usage.total_generations) > 0) && (
            <ClaimCard
              title={`This month: ${formatTokens(usage.total_tokens)} tokens across ${Number(usage.total_generations) || 0} generations`}
              why="Your usage is private to you — it only informs budget alerts, never what I remember."
              action={
                <Button size="small" variant="outlined" onClick={onShowUsage} sx={{ fontSize: '0.7rem', minWidth: 0, whiteSpace: 'nowrap' }}>
                  Open usage
                </Button>
              }
            />
          )}
        </Stack>
      )}
    </Box>
  );
}

export default AIRelationshipTab;
