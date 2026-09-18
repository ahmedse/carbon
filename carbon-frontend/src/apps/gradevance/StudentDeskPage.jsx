// Student desk — paste draft → formative analyze → coaching + LCT SD/SG report.

import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem, Paper, Select, Stack, TextField, Typography,
} from '@mui/material';
import EditNoteIcon from '@mui/icons-material/EditNote';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  createAssignment, fetchDemoExamples, fetchProfiles, submitAndAnalyze,
} from '../../api/gradevance';
import SkipToMain from './SkipToMain';
import WaveChart from './WaveChart';
import LctCodesTable from './LctCodesTable';

const DEFAULT_PROFILE = 'naa_cycle1_exam_prep';

export default function StudentDeskPage() {
  useDocumentTitle('GradeVance · Student');
  const { token } = useAuth();
  const [searchParams] = useSearchParams();
  const linkedAssignmentId = useMemo(
    () => (searchParams.get('assignment') || '').trim(),
    [searchParams],
  );
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [run, setRun] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [packId, setPackId] = useState(DEFAULT_PROFILE);
  const [examples, setExamples] = useState([]);
  const [exampleId, setExampleId] = useState('');

  useEffect(() => {
    fetchProfiles(token)
      .then((data) => {
        const rows = data.results || [];
        setProfiles(rows);
        if (rows.length && !rows.some((p) => p.pack_id === packId)) {
          setPackId(rows[0].pack_id);
        }
      })
      .catch(() => {});
    fetchDemoExamples(token)
      .then((data) => setExamples(data.results || []))
      .catch(() => {});
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps -- initial catalog load

  const loadExample = (id) => {
    setExampleId(id);
    const ex = examples.find((e) => e.id === id);
    if (!ex) return;
    setText(ex.text);
    setPackId(ex.profile_pack_id || DEFAULT_PROFILE);
    setRun(null);
    setError(null);
  };

  const onAnalyze = async () => {
    setBusy(true);
    setError(null);
    setRun(null);
    try {
      let assignmentId = linkedAssignmentId;
      if (!assignmentId) {
        const selected = profiles.find((p) => p.pack_id === packId);
        const assignment = await createAssignment(token, {
          title: 'Formative practice',
          mode: 'formative',
          status: 'published',
          profile_pack_id: packId || DEFAULT_PROFILE,
          profile_version: selected?.version || 1,
        });
        assignmentId = assignment.id;
      }
      const result = await submitAndAnalyze(token, {
        assignment: assignmentId,
        text,
      });
      setRun(result.run);
    } catch (err) {
      setError(err?.message || 'Analysis failed');
    } finally {
      setBusy(false);
    }
  };

  const bands = run?.advisory_bands || {};
  const coaching = run?.coaching || {};

  return (
    <PageContainer>
      <SkipToMain targetId="gradevance-student" />
      <Box component="main" id="gradevance-student" tabIndex={-1} aria-label="Student desk">
        <PageHeader
          icon={EditNoteIcon}
          title="Student desk"
          subtitle="Load a gold/raw example or paste a draft → formative LCT (SG/SD) + coaching."
        />
        {linkedAssignmentId && (
          <Alert severity="info" sx={{ mb: 2 }} role="status">
            Linked assignment {linkedAssignmentId} (LTI deep link)
          </Alert>
        )}
        <Stack
          spacing={2}
          component="form"
          onSubmit={(e) => { e.preventDefault(); onAnalyze(); }}
          aria-label="Formative reflection submission"
        >
          {!linkedAssignmentId && examples.length > 0 && (
            <FormControl fullWidth size="small">
              <InputLabel id="student-example-label">Demo example (from packs)</InputLabel>
              <Select
                labelId="student-example-label"
                label="Demo example (from packs)"
                value={exampleId}
                onChange={(e) => loadExample(e.target.value)}
                displayEmpty
              >
                <MenuItem value="">
                  <em>Choose a gold / held-out sample…</em>
                </MenuItem>
                {examples.map((ex) => (
                  <MenuItem key={ex.id} value={ex.id}>
                    {ex.title} ({ex.word_count} words)
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          {!linkedAssignmentId && (
            <FormControl fullWidth size="small">
              <InputLabel id="student-profile-label">Practice profile</InputLabel>
              <Select
                labelId="student-profile-label"
                label="Practice profile"
                value={packId}
                onChange={(e) => setPackId(e.target.value)}
              >
                {(profiles.length ? profiles : [{ pack_id: DEFAULT_PROFILE, name: DEFAULT_PROFILE }]).map((p) => (
                  <MenuItem key={p.pack_id} value={p.pack_id}>
                    {p.name || p.pack_id}
                    {p.discipline ? ` (${p.discipline})` : ''}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          <TextField
            label="Your reflection"
            multiline
            minRows={8}
            fullWidth
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Write 200–300 words using WHAT / SO WHAT / NOW WHAT…"
            inputProps={{ 'aria-describedby': 'reflection-hint' }}
          />
          <Typography id="reflection-hint" variant="caption" color="text.secondary">
            Minimum ~40 characters. Results are advisory until a marker releases summative marks.
          </Typography>
          <Box>
            <Button
              type="submit"
              variant="contained"
              disabled={busy || text.trim().length < 40}
              aria-busy={busy}
            >
              {busy ? 'Analyzing…' : 'Run formative analysis'}
            </Button>
          </Box>
          {error && <Alert severity="error">{error}</Alert>}
          {run && (
            <Paper sx={{ p: 2 }}>
              <Stack direction="row" spacing={1} sx={{ mb: 1 }} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="h6">Result</Typography>
                <Chip size="small" label={run.status} />
                <Chip size="small" label={`gate: ${run.gate_decision}`} />
                {coaching.watermark && <Chip size="small" color="warning" label={coaching.watermark} />}
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Confidence {run.mean_confidence ?? '—'} · segments {run.segments?.length ?? 0}
              </Typography>
              <Typography variant="subtitle2">Advisory bands</Typography>
              <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap' }} useFlexGap>
                {Object.entries(bands).map(([k, v]) => (
                  <Chip key={k} label={`${k}: ${v}`} />
                ))}
              </Stack>
              <Typography variant="subtitle2">Strengths</Typography>
              <ul>
                {(coaching.strengths || []).map((s) => (
                  <li key={s}><Typography variant="body2">{s}</Typography></li>
                ))}
              </ul>
              <Typography variant="subtitle2">Diagnosis → Action</Typography>
              <ul>
                {(coaching.diagnosis_actions || []).map((d) => (
                  <li key={d.id || d.diagnosis}>
                    <Typography variant="body2"><strong>{d.diagnosis}</strong> — {d.action}</Typography>
                  </li>
                ))}
              </ul>
              <LctCodesTable segments={run.segments || []} wave={run.wave} />
              {run.wave?.points?.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2">Semantic wave (SG)</Typography>
                  <WaveChart points={run.wave.points} />
                </Box>
              )}
            </Paper>
          )}
        </Stack>
      </Box>
    </PageContainer>
  );
}
