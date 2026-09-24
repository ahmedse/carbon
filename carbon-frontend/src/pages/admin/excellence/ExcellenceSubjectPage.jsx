import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, CircularProgress, Link, Stack, Table, TableBody, TableCell,
  TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { apiFetch } from '../../../api/api';
import PageContainer from '../../../components/layout/PageContainer';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { levelColor, stateColor } from './excellenceUi';

function PathList({ label, items }) {
  if (!items?.length) return null;
  return (
    <Typography variant="body2" sx={{ mb: 0.5 }}>
      <strong>{label}:</strong> {items.map((p) => <code key={p} style={{ marginRight: 8 }}>{p}</code>)}
    </Typography>
  );
}

function defaultUntil() {
  const d = new Date();
  d.setDate(d.getDate() + 30);
  return d.toISOString().slice(0, 10);
}

export default function ExcellenceSubjectPage() {
  const { token } = useAuth();
  const { subjectId } = useParams();
  const [subject, setSubject] = useState(null);
  const [error, setError] = useState(null);
  const [exemptCheck, setExemptCheck] = useState('');
  const [exemptReason, setExemptReason] = useState('');
  const [exemptUntil, setExemptUntil] = useState(defaultUntil);
  const [busy, setBusy] = useState(false);
  useDocumentTitle(subject?.title || 'Excellence subject');

  const reload = useCallback(() => {
    if (!token || !subjectId) return Promise.resolve();
    return apiFetch(`excellence/subjects/${encodeURIComponent(subjectId)}/`, { token })
      .then(setSubject)
      .catch((err) => setError(err?.message || 'Subject failed to load'));
  }, [token, subjectId]);

  useEffect(() => {
    if (!token || !subjectId) return undefined;
    let cancelled = false;
    setSubject(null);
    setError(null);
    apiFetch(`excellence/subjects/${encodeURIComponent(subjectId)}/`, { token })
      .then((data) => { if (!cancelled) setSubject(data); })
      .catch((err) => { if (!cancelled) setError(err?.message || 'Subject failed to load'); });
    return () => { cancelled = true; };
  }, [token, subjectId]);

  async function grantExemption() {
    if (!token || !exemptCheck || !exemptReason || busy) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch('excellence/exemptions/', {
        token,
        method: 'POST',
        body: {
          check_id: exemptCheck,
          subject_id: subjectId,
          reason: exemptReason,
          until: exemptUntil,
        },
      });
      setExemptReason('');
      await reload();
    } catch (err) {
      setError(err?.message || 'Could not grant exemption');
    } finally {
      setBusy(false);
    }
  }

  async function revokeExemption(id) {
    if (!token || busy) return;
    setBusy(true);
    try {
      await apiFetch(`excellence/exemptions/${id}/`, { token, method: 'DELETE' });
      await reload();
    } catch (err) {
      setError(err?.message || 'Could not revoke exemption');
    } finally {
      setBusy(false);
    }
  }

  const grantable = (subject?.checks || []).filter((c) => !['passed', 'exempt'].includes(c.state));

  return (
    <PageContainer>
      <Link component={RouterLink} to={subject ? `/admin/excellence/${subject.tier}${subject.track ? `/${subject.track}` : ''}` : '/admin/excellence'}>
        ← Ladder
      </Link>
      {error && <Alert severity="error" sx={{ my: 1 }}>{error}</Alert>}
      {!subject && !error && <CircularProgress size={28} sx={{ display: 'block', my: 2 }} />}
      {subject && (
        <>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ my: 1 }} flexWrap="wrap">
            <Typography variant="h6">{subject.title}</Typography>
            <Chip size="small" color={levelColor(subject.level)} label={`L${subject.level} ${subject.level_name}`} />
            <Chip size="small" variant="outlined" label={subject.kind} />
            <Chip size="small" variant="outlined" label={subject.owner || 'no owner'} color={subject.owner ? 'default' : 'error'} />
          </Stack>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
            {subject.subject_id} · {subject.tier}{subject.track ? ` / ${subject.track}` : ''} · HEAD {subject.head?.slice(0, 7) || '?'}
          </Typography>
          <PathList label="Paths" items={subject.paths} />
          <PathList label="Tests" items={subject.tests} />
          <PathList label="Spec" items={subject.spec} />
          <PathList label="ADR" items={subject.adr} />

          <Typography variant="subtitle2" sx={{ mt: 2, mb: 0.5 }}>Checks</Typography>
          <Box sx={{ overflow: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Rank</TableCell>
                  <TableCell>Check</TableCell>
                  <TableCell>Dimension</TableCell>
                  <TableCell>State</TableCell>
                  <TableCell>Evidence</TableCell>
                  <TableCell>How to earn it</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {subject.checks.map((c) => (
                  <TableRow key={c.check_id} selected={subject.next.includes(c.check_id)}>
                    <TableCell>L{c.rank}</TableCell>
                    <TableCell>
                      {c.title}
                      <Typography variant="caption" color="text.secondary" display="block">{c.check_id}</Typography>
                    </TableCell>
                    <TableCell>{c.dimension}</TableCell>
                    <TableCell><Chip size="small" color={stateColor(c.state)} label={c.state} /></TableCell>
                    <TableCell>
                      {c.evidence_class}
                      {c.source && <Typography variant="caption" color="text.secondary" display="block">{c.source}</Typography>}
                    </TableCell>
                    <TableCell><Typography variant="body2">{c.solution || '—'}</Typography></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>

          <Typography variant="subtitle2" sx={{ mt: 2, mb: 0.5 }}>Exemptions</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Exemptions expire. Seat masters grant for their tree; they never become a permanent green.
          </Typography>
          {subject.exemptions.map((x) => (
            <Alert
              key={x.id || x.check_id}
              severity="info"
              sx={{ mb: 0.5 }}
              action={(
                <Button color="inherit" size="small" onClick={() => revokeExemption(x.id)} disabled={busy || !x.id}>
                  Revoke
                </Button>
              )}
            >
              <strong>{x.check_id}</strong> until {x.until} — {x.reason} ({x.granted_by})
            </Alert>
          ))}
          {grantable.length > 0 && (
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mt: 1 }} alignItems="flex-start">
              <TextField
                select
                SelectProps={{ native: true }}
                size="small"
                label="Check"
                value={exemptCheck}
                onChange={(e) => setExemptCheck(e.target.value)}
                sx={{ minWidth: 220 }}
              >
                <option value="" />
                {grantable.map((c) => (
                  <option key={c.check_id} value={c.check_id}>{c.check_id} · {c.state}</option>
                ))}
              </TextField>
              <TextField
                size="small"
                label="Reason"
                value={exemptReason}
                onChange={(e) => setExemptReason(e.target.value)}
                sx={{ flex: 1, minWidth: 200 }}
              />
              <TextField
                size="small"
                type="date"
                label="Until"
                InputLabelProps={{ shrink: true }}
                value={exemptUntil}
                onChange={(e) => setExemptUntil(e.target.value)}
              />
              <Button variant="outlined" size="small" onClick={grantExemption} disabled={busy || !exemptCheck || !exemptReason}>
                Grant
              </Button>
            </Stack>
          )}

          <Typography variant="subtitle2" sx={{ mt: 2, mb: 0.5 }}>Trend</Typography>
          {subject.trend.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No snapshots yet (<code>--write</code> freezes one per day).</Typography>
          ) : (
            <Stack direction="row" spacing={0.5} flexWrap="wrap">
              {subject.trend.map((t) => (
                <Chip key={t.date} size="small" variant="outlined" color={levelColor(t.level)} label={`${t.date} · L${t.level}`} />
              ))}
            </Stack>
          )}

          <Typography variant="subtitle2" sx={{ mt: 2, mb: 0.5 }}>Recent evidence</Typography>
          <Box sx={{ overflow: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>When</TableCell>
                  <TableCell>Check</TableCell>
                  <TableCell>Result</TableCell>
                  <TableCell>Commit</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {subject.events.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>{e.at ? new Date(e.at).toLocaleString() : '—'}</TableCell>
                    <TableCell>{e.check_id}</TableCell>
                    <TableCell><Chip size="small" color={stateColor(e.result)} label={e.result} /></TableCell>
                    <TableCell><code>{(e.commit || '').slice(0, 7)}</code></TableCell>
                    <TableCell>{e.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        </>
      )}
    </PageContainer>
  );
}
