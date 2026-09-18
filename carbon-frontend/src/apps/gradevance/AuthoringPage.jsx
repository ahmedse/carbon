// Authoring — publish Assignment from a pack profile.

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, FormControl, InputLabel, MenuItem, Select, Stack, TextField, Typography,
} from '@mui/material';
import CreateIcon from '@mui/icons-material/Create';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  createAssignment, fetchProfiles, fetchPublishGate, previewDeepLink,
} from '../../api/gradevance';
import SkipToMain from './SkipToMain';

export default function AuthoringPage() {
  useDocumentTitle('GradeVance · Authoring');
  const { token } = useAuth();
  const [profiles, setProfiles] = useState([]);
  const [packId, setPackId] = useState('');
  const [title, setTitle] = useState('');
  const [mode, setMode] = useState('formative');
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [gate, setGate] = useState(null);
  const [lastAssignmentId, setLastAssignmentId] = useState(null);
  const [deepLink, setDeepLink] = useState(null);

  const load = useCallback(() => {
    fetchProfiles(token)
      .then((data) => {
        const rows = data.results || [];
        setProfiles(rows);
        if (rows.length && !packId) setPackId(rows[0].pack_id);
      })
      .catch((e) => setErr(e?.message));
  }, [token, packId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!packId || !token) return;
    const selected = profiles.find((p) => p.pack_id === packId);
    fetchPublishGate(token, packId, selected?.version)
      .then(setGate)
      .catch(() => setGate(null));
  }, [packId, profiles, token]);

  const onPublish = async () => {
    setErr(null);
    setMsg(null);
    try {
      const selected = profiles.find((p) => p.pack_id === packId);
      const asg = await createAssignment(token, {
        title: title || selected?.name || packId,
        mode,
        status: 'published',
        profile_pack_id: packId,
        profile_version: selected?.version || 1,
      });
      setMsg(`Published assignment ${asg.id} → profile ${packId}@v${selected?.version || 1}`);
      setLastAssignmentId(asg.id);
      setDeepLink(null);
      setTitle('');
    } catch (e) {
      setErr(e?.message || 'Publish failed');
    }
  };

  const onDeepLink = async () => {
    if (!lastAssignmentId) return;
    setErr(null);
    try {
      const dl = await previewDeepLink(token, { assignment_id: lastAssignmentId });
      setDeepLink(dl);
    } catch (e) {
      setErr(e?.message || 'Deep link preview failed');
    }
  };

  return (
    <PageContainer>
      <SkipToMain targetId="gradevance-authoring" />
      <Box component="main" id="gradevance-authoring" tabIndex={-1} aria-label="Assignment authoring">
      <PageHeader
        icon={CreateIcon}
        title="Authoring"
        subtitle="Pin an AssignmentProfile — pipeline snapshot freezes at publish. Summative LCT packs need κ gate."
      />
      <Stack spacing={2} sx={{ maxWidth: 520 }} component="form" onSubmit={(e) => { e.preventDefault(); onPublish(); }} aria-label="Publish assignment form">
        <FormControl fullWidth>
          <InputLabel id="profile-label">Profile pack</InputLabel>
          <Select
            labelId="profile-label"
            label="Profile pack"
            value={packId}
            onChange={(e) => setPackId(e.target.value)}
          >
            {profiles.map((p) => (
              <MenuItem key={p.pack_id} value={p.pack_id}>
                {p.name || p.pack_id} ({p.discipline}/{p.genre}) {p.lct_enabled ? '· LCT' : '· LCT off'}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField label="Assignment title" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
        <FormControl fullWidth>
          <InputLabel id="mode-label">Mode</InputLabel>
          <Select labelId="mode-label" label="Mode" value={mode} onChange={(e) => setMode(e.target.value)}>
            <MenuItem value="formative">Formative</MenuItem>
            <MenuItem value="summative">Summative (HITL release + κ gate)</MenuItem>
            <MenuItem value="calibration">Calibration</MenuItem>
          </Select>
        </FormControl>
        {gate && (
          <Alert severity={gate.required && !gate.passed ? 'warning' : 'info'}>
            Publish gate: {gate.required ? (gate.passed ? 'PASS' : 'FAIL') : 'not required'}
            {gate.required && gate.reliability
              ? ` · κ=${gate.reliability.value} (min ${gate.minimum_kappa}) · n=${gate.held_out_n}`
              : ''}
            {gate.reason ? ` — ${gate.reason}` : ''}
          </Alert>
        )}
        <Button
          type="submit"
          variant="contained"
          disabled={!packId || (mode === 'summative' && gate?.required && !gate?.passed)}
        >
          Publish assignment
        </Button>
        {msg && <Alert severity="success" role="status">{msg}</Alert>}
        {err && <Alert severity="error" role="alert">{err}</Alert>}
        {lastAssignmentId && (
          <Button variant="outlined" onClick={onDeepLink}>
            Preview LMS deep link
          </Button>
        )}
        {deepLink?.content_item && (
          <Alert severity="info" role="status">
            <Typography variant="body2" component="pre" sx={{ m: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
              {JSON.stringify(deepLink.content_item, null, 2)}
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1 }}>
              {deepLink.note}
            </Typography>
          </Alert>
        )}
        <Typography variant="caption" color="text.secondary" id="authoring-help">
          Summative marks stay draft until a marker releases. Intelligence promotions never rewrite released cohorts.
        </Typography>
      </Stack>
      </Box>
    </PageContainer>
  );
}
