import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Alert, Button, Chip, Link, Skeleton, Stack, TextField, Typography,
} from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { apiFetch } from '../../../api/api';
import PageContainer from '../../../components/layout/PageContainer';
import FilteredDataGrid from '../../../components/FilteredDataGrid';
import { SearchSelect } from '../../../components/Form';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { levelColor, stateColor } from './excellenceUi';

function PathList({ label, items }) {
  if (!items?.length) return null;
  return (
    <Typography variant="body2" sx={{ mb: 0.5 }}>
      <strong>{label}:</strong> {items.map((p) => (
        <Typography key={p} component="span" variant="body2" sx={{ mr: 1 }}><code>{p}</code></Typography>
      ))}
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
      <Link component={RouterLink} to={subject ? `/admin/excellence/${subject.tier}/${encodeURIComponent(subject.tier === 'pulse' ? 'pulse' : subject.subject_id)}` : '/admin/excellence'}>
        Back to app
      </Link>
      {error && <Alert severity="error" sx={{ my: 1 }}>{error}</Alert>}
      {!subject && !error && (
        <Stack spacing={1} aria-busy="true" aria-label="Loading subject" sx={{ my: 2 }}>
          <Skeleton variant="rounded" sx={{ height: 4 }} />
          <Skeleton variant="rounded" sx={{ height: 22 }} />
        </Stack>
      )}
      {subject && (
        <>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ my: 1 }} flexWrap="wrap">
            <Typography variant="h6">{subject.title}</Typography>
            <Chip size="small" color={levelColor(subject.level)} label={subject.level_name} />
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

          <FilteredDataGrid
            embedded
            title="Checks"
            rows={subject.checks || []}
            getRowId={(row) => row.check_id}
            highlightRow={(row) => (subject.next || []).includes(row.check_id)}
            columns={[
              { field: 'rank', headerName: 'Level', width: 90, valueGetter: (_v, row) => row.rank },
              { field: 'title', headerName: 'Check', flex: 1, minWidth: 180 },
              { field: 'dimension', headerName: 'Aspect', width: 140 },
              { field: 'state', headerName: 'State', width: 130, renderCell: (p) => <Chip size="small" color={stateColor(p.value)} label={p.value} /> },
              { field: 'evidence_class', headerName: 'Evidence', width: 160 },
              { field: 'solution', headerName: 'How to earn it', flex: 1, minWidth: 180 },
            ]}
            emptyMessage="No checks bound"
          />

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
              <SearchSelect
                label="Check"
                options={grantable.map((c) => ({ value: c.check_id, label: `${c.check_id} · ${c.state}` }))}
                value={exemptCheck}
                onChange={(opt) => setExemptCheck(opt?.value || '')}
                sx={{ minWidth: 220 }}
              />
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

          <FilteredDataGrid
            embedded
            title="Recent evidence"
            rows={subject.events || []}
            getRowId={(row) => row.id}
            columns={[
              { field: 'at', headerName: 'When', width: 180, valueGetter: (_v, row) => (row.at ? new Date(row.at).toLocaleString() : '—') },
              { field: 'check_id', headerName: 'Check', flex: 1, minWidth: 140 },
              { field: 'result', headerName: 'Result', width: 130, renderCell: (p) => <Chip size="small" color={stateColor(p.value)} label={p.value} /> },
              { field: 'commit', headerName: 'Commit', width: 110, valueGetter: (_v, row) => (row.commit || '').slice(0, 7) },
              { field: 'source', headerName: 'Source', flex: 1, minWidth: 140 },
            ]}
            emptyMessage="No evidence yet"
          />
        </>
      )}
    </PageContainer>
  );
}
