// src/pages/admin/ai/ReviewQueue.jsx
// Route /admin/ai/review-queue — P3-05c Review Queue. Lists processes in
// `status=review` and renders the SEVEN review dimensions, each from real
// data (no fabricated content):
//   1. Diff (vs active)            2. Rationale (objective)
//   3. Evidence                    4. Missing evidence (derived)
//   5. Permissions delta (derived) 6. Tests
//   7. Affected runs (current user only)
//
// Reject-by-note is explicitly NOTE-ONLY — there is no backend reject
// endpoint, so the note is never persisted server-side. Publish maps to
// ai:publisher (server refuses self-publish with 403 {error, detail}).
// RULE_8 tokens only; RULE_10 apiFetch only.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
  useTheme,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import RefreshIcon from '@mui/icons-material/Refresh';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { AI_PUBLISHER, hasAnyCap } from '../../../capabilities';
import { getDiff, getProcess, listProcesses, publishProcess } from '../../../api/aiRegistry';
import { listPlans } from '../../../api/aiWorkspace';

function formatTimestamp(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

export function capabilityKeys(caps) {
  if (!Array.isArray(caps)) return [];
  return caps
    .map((c) =>
      typeof c === 'string' ? c : c?.key || c?.capability || c?.code || ''
    )
    .filter(Boolean);
}

export function objectiveText(def) {
  const o = def?.objective;
  if (!o) return '—';
  if (typeof o === 'string') return o;
  if (o && typeof o === 'object' && o.predicate) return o.predicate;
  return JSON.stringify(o);
}

/** Compact flatten of a recursive registry diff for inline rendering. */
function flattenDiff(added, removed, changed, prefix = '') {
  const out = [];
  for (const key of Object.keys(added || {})) {
    out.push({ kind: 'added', label: prefix ? `${prefix}.${key}` : key, value: added[key] });
  }
  for (const key of Object.keys(removed || {})) {
    out.push({ kind: 'removed', label: prefix ? `${prefix}.${key}` : key, value: removed[key] });
  }
  for (const key of Object.keys(changed || {})) {
    const entry = changed[key];
    const label = prefix ? `${prefix}.${key}` : key;
    if (
      entry &&
      typeof entry === 'object' &&
      !Array.isArray(entry) &&
      'from' in entry &&
      'to' in entry
    ) {
      out.push({ kind: 'changed', label, from: entry.from, to: entry.to });
    } else if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
      out.push(...flattenDiff(entry.added, entry.removed, entry.changed, label));
    }
  }
  return out;
}

/** Does any evidence entry reference this step id (by step/step_id/ref or text)? */
export function evidenceReferencesStep(evidence, stepId) {
  if (!Array.isArray(evidence)) return false;
  return evidence.some((e) => {
    if (typeof e === 'string') return e === stepId || e.includes(stepId);
    if (e && typeof e === 'object') {
      if ([e.step, e.step_id, e.stepId, e.ref, e.reference].some((v) => v === stepId)) {
        return true;
      }
      return JSON.stringify(e).includes(stepId);
    }
    return false;
  });
}

/**
 * Derive missing evidence: for each step with kind==='human_task' or
 * consent===true, if no evidence entry references that step id → missing.
 */
export function deriveMissingEvidence(definition) {
  const steps = Array.isArray(definition?.steps) ? definition.steps : [];
  const evidence = Array.isArray(definition?.evidence) ? definition.evidence : [];
  const missing = [];
  for (const step of steps) {
    if (!step || !step.id) continue;
    if (step.kind === 'human_task' || step.consent === true) {
      if (!evidenceReferencesStep(evidence, step.id)) missing.push(step.id);
    }
  }
  return missing;
}

/**
 * Permissions delta: from `diff.changed.steps` ({from, to} step arrays), match
 * steps by id and surface capability / separation_of_duties changes.
 */
export function computePermissionDelta(diff) {
  if (!diff || !diff.changed) return [];
  const stepsChange = diff.changed.steps;
  if (!stepsChange || typeof stepsChange !== 'object' || Array.isArray(stepsChange)) {
    return [];
  }
  const fromArr = Array.isArray(stepsChange.from) ? stepsChange.from : [];
  const toArr = Array.isArray(stepsChange.to) ? stepsChange.to : [];
  const fromById = new Map(
    fromArr.filter((s) => s && s.id).map((s) => [s.id, s])
  );
  const deltas = [];
  for (const next of toArr) {
    if (!next || !next.id) continue;
    const prev = fromById.get(next.id);
    if (!prev) continue;
    if ((prev.capability ?? null) !== (next.capability ?? null)) {
      deltas.push({
        step: next.id,
        field: 'capability',
        from: prev.capability ?? null,
        to: next.capability ?? null,
      });
    }
    const prevSod = JSON.stringify(prev.separation_of_duties ?? null);
    const nextSod = JSON.stringify(next.separation_of_duties ?? null);
    if (prevSod !== nextSod) {
      deltas.push({
        step: next.id,
        field: 'separation_of_duties',
        from: prev.separation_of_duties ?? null,
        to: next.separation_of_duties ?? null,
      });
    }
  }
  return deltas;
}

function jsonLine(value) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function Dimension({ label, children }) {
  return (
    <Stack spacing={0.5}>
      <Typography variant="overline" sx={{ lineHeight: 1 }}>
        {label}
      </Typography>
      {children}
    </Stack>
  );
}

export default function ReviewQueue() {
  useDocumentTitle('Review Queue');
  const theme = useTheme();
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const caps = useMemo(() => capabilityKeys(userCapabilities), [userCapabilities]);
  const isPublisher = useMemo(() => hasAnyCap(caps, [AI_PUBLISHER]), [caps]);

  const [items, setItems] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [acting, setActing] = useState(false);
  const [notes, setNotes] = useState({});
  const [savedNotes, setSavedNotes] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, plansResp] = await Promise.all([
        listProcesses(token, { status: 'review' }),
        listPlans(token),
      ]);
      const reviewRows = Array.isArray(rows) ? rows : [];
      const planList = Array.isArray(plansResp?.plans) ? plansResp.plans : [];
      setPlans(planList);
      const enriched = await Promise.all(
        reviewRows.map(async (row) => {
          try {
            const [definition, diff] = await Promise.all([
              getProcess(token, row.process_id),
              getDiff(token, row.process_id),
            ]);
            return { ...row, definition: definition?.definition, diff };
          } catch {
            return { ...row, definition: null, diff: null };
          }
        })
      );
      setItems(enriched);
      setOffline(false);
    } catch {
      setItems([]);
      setPlans([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const doPublish = async (id) => {
    setActing(true);
    try {
      await publishProcess(token, id);
      notify({ message: `Published ${id}.`, type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Publish failed');
    } finally {
      setActing(false);
    }
  };

  const saveNote = (id) => {
    setSavedNotes((prev) => ({ ...prev, [id]: true }));
    notify({ message: 'Note saved (local only — no server state change).', type: 'info' });
  };

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h5">Review Queue</Typography>
          <Button startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
            Refresh
          </Button>
        </Stack>

        {offline && (
          <Paper sx={{ p: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
            <CloudOffIcon color="disabled" />
            <Typography variant="body2">
              Review queue is temporarily unavailable.
            </Typography>
          </Paper>
        )}

        {loading ? (
          <Stack alignItems="center" sx={{ py: 6 }}>
            <CircularProgress />
          </Stack>
        ) : items.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              No processes awaiting review.
            </Typography>
          </Paper>
        ) : (
          <Stack spacing={2}>
            {items.map((item) => {
              const def = item.definition || {};
              const missing = deriveMissingEvidence(def);
              const permDelta = computePermissionDelta(item.diff);
              const runs = plans.filter(
                (p) => p.definition_id === item.process_id
              );
              const diffLines = flattenDiff(
                item.diff?.added,
                item.diff?.removed,
                item.diff?.changed
              );
              return (
                <Paper key={item.process_id} sx={{ p: 2 }} variant="outlined">
                  <Stack spacing={1.5}>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                      <Typography variant="subtitle1">{item.process_id}</Typography>
                      <Chip size="small" label={item.status} variant="outlined" />
                      <Typography variant="body2" color="text.secondary">
                        v{item.version} · {item.owner} · {formatTimestamp(item.updated_at)}
                      </Typography>
                    </Stack>

                    {/* 1. Diff */}
                    <Dimension label="Diff">
                      {!item.diff ? (
                        <Typography variant="body2" color="text.secondary">
                          Diff unavailable.
                        </Typography>
                      ) : item.diff.diff === null ? (
                        <Typography variant="body2" color="text.secondary">
                          No active version to diff against.
                        </Typography>
                      ) : diffLines.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                          No differences vs active.
                        </Typography>
                      ) : (
                        <Stack spacing={0.25}>
                          {diffLines.map((line, i) => {
                            const color =
                              line.kind === 'added'
                                ? theme.palette.success.main
                                : line.kind === 'removed'
                                  ? theme.palette.error.main
                                  : theme.palette.warning.main;
                            const text =
                              line.kind === 'changed'
                                ? `${jsonLine(line.from)} → ${jsonLine(line.to)}`
                                : jsonLine(line.value);
                            return (
                              <Typography
                                key={i}
                                variant="body2"
                                sx={{
                                  fontSize: '0.72rem',
                                  color,
                                  textDecorationLine:
                                    line.kind === 'removed' ? 'line-through' : 'none',
                                  wordBreak: 'break-word',
                                }}
                              >
                                {line.kind === 'added' ? '+ ' : line.kind === 'removed' ? '- ' : '~ '}
                                {line.label}: {text}
                              </Typography>
                            );
                          })}
                        </Stack>
                      )}
                    </Dimension>

                    {/* 2. Rationale */}
                    <Dimension label="Rationale">
                      <Typography variant="body2">{objectiveText(def)}</Typography>
                    </Dimension>

                    {/* 3. Evidence */}
                    <Dimension label="Evidence">
                      {Array.isArray(def.evidence) && def.evidence.length > 0 ? (
                        <Stack spacing={0.25}>
                          {def.evidence.map((e, i) => (
                            <Typography key={i} variant="body2" sx={{ fontSize: '0.72rem' }}>
                              • {jsonLine(e)}
                            </Typography>
                          ))}
                        </Stack>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          No evidence provided.
                        </Typography>
                      )}
                    </Dimension>

                    {/* 4. Missing evidence (derived) */}
                    <Dimension label="Missing evidence">
                      {missing.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                          No missing evidence.
                        </Typography>
                      ) : (
                        <Typography variant="body2">
                          {missing.join(', ')}
                        </Typography>
                      )}
                      <Typography variant="caption" color="text.secondary">
                        Derived rule: any step with kind="human_task" or consent=true
                        whose id is not referenced by any evidence entry.
                      </Typography>
                    </Dimension>

                    {/* 5. Permissions delta (derived) */}
                    <Dimension label="Permissions delta">
                      {permDelta.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                          No permission changes vs active.
                        </Typography>
                      ) : (
                        <Stack spacing={0.25}>
                          {permDelta.map((d, i) => (
                            <Typography key={i} variant="body2" sx={{ fontSize: '0.72rem' }}>
                              • {d.step}.{d.field}: {jsonLine(d.from)} → {jsonLine(d.to)}
                            </Typography>
                          ))}
                        </Stack>
                      )}
                    </Dimension>

                    {/* 6. Tests */}
                    <Dimension label="Tests">
                      {Array.isArray(def.tests) && def.tests.length > 0 ? (
                        <Stack spacing={0.25}>
                          {def.tests.map((t, i) => (
                            <Typography key={i} variant="body2" sx={{ fontSize: '0.72rem' }}>
                              • {jsonLine(t)}
                            </Typography>
                          ))}
                        </Stack>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          No tests declared.
                        </Typography>
                      )}
                    </Dimension>

                    {/* 7. Affected runs */}
                    <Dimension label="Affected runs">
                      {runs.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                          No runs for the current user referencing this process.
                        </Typography>
                      ) : (
                        <Stack spacing={0.25}>
                          {runs.map((r) => (
                            <Typography key={r.id} variant="body2" sx={{ fontSize: '0.72rem' }}>
                              • {r.id} ({r.status}) — {r.brief || '—'} · {formatTimestamp(r.created_at)}
                            </Typography>
                          ))}
                        </Stack>
                      )}
                      <Typography variant="caption" color="text.secondary">
                        Runs for the current user referencing this process (the plans
                        list is owner-scoped; cross-user runs are not visible here).
                      </Typography>
                    </Dimension>

                    {/* Actions */}
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                      <Button
                        size="small"
                        variant="contained"
                        color="success"
                        disabled={acting || !isPublisher}
                        onClick={() => doPublish(item.process_id)}
                        title={isPublisher ? '' : 'Requires ai:publisher'}
                      >
                        Publish
                      </Button>
                      <TextField
                        size="small"
                        label="Reject note (note only — no server state change)"
                        value={notes[item.process_id] || ''}
                        onChange={(e) =>
                          setNotes((prev) => ({ ...prev, [item.process_id]: e.target.value }))
                        }
                        sx={{ flex: 1, minWidth: 260 }}
                      />
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => saveNote(item.process_id)}
                        disabled={!notes[item.process_id]}
                      >
                        {savedNotes[item.process_id] ? 'Note saved (local only)' : 'Save note'}
                      </Button>
                    </Stack>
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        )}
      </Stack>
    </PageContainer>
  );
}
