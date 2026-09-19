// Calibration — held-out expert vs engine + κ (prove the instrument).

import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem, Paper, Select,
  Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import VerifiedIcon from '@mui/icons-material/Verified';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import SystemDialog from '../../components/SystemDialog';
import SegmentationEditor, { suggestSplitPoints, buildSegDraft } from '../../components/gradevance/SegmentationEditor';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchCalibration, fetchProfiles, proposeCalibrationSegmentation, suggestSegmentationSplits } from '../../api/gradevance';
import SkipToMain from './SkipToMain';

export default function CalibrationPage() {
  const { pathname } = useLocation();
  const titlePrefix = pathname.startsWith('/teach') ? 'Teach' : 'GradeVance';
  useDocumentTitle(`${titlePrefix} · Calibration`);
  const { token } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const [profiles, setProfiles] = useState([]);
  const [packId, setPackId] = useState(params.get('profile_pack_id') || 'naa_cycle1_exam_prep');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [essayOpen, setEssayOpen] = useState(false);
  const [essay, setEssay] = useState(null);
  const [segDraft, setSegDraft] = useState(null);
  const [segRationale, setSegRationale] = useState('');
  const [segKey, setSegKey] = useState(0);
  const [segSuggestions, setSegSuggestions] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadProfiles = useCallback(() => {
    fetchProfiles(token)
      .then((p) => {
        const rows = p.results || [];
        setProfiles(rows);
        if (rows.length && !rows.some((x) => x.pack_id === packId)) {
          setPackId(rows[0].pack_id);
        }
      })
      .catch(() => {});
  }, [token, packId]);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchCalibration(token, { profile_pack_id: packId, profile_version: 1 })
      .then((d) => setData(d))
      .catch((e) => setError(e?.message || 'Failed to load calibration'))
      .finally(() => setLoading(false));
  }, [token, packId]);

  useEffect(() => { loadProfiles(); }, [loadProfiles]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('profile_pack_id', packId);
      return next;
    }, { replace: true });
  }, [packId, setParams]);

  const openEssayResegment = (row) => {
    setEssay(row);
    setSegDraft(row.expert_segments || []);
    setSegRationale('');
    setSegSuggestions(null);
    setSegKey((k) => k + 1);
    setEssayOpen(true);
  };

  const saveEssayResegment = async () => {
    if (!essay || !segRationale.trim() || !segDraft?.length) {
      setError('Rationale and segments required');
      return;
    }
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await proposeCalibrationSegmentation(token, {
        example_id: essay.example_id,
        segments: segDraft,
        rationale: segRationale.trim(),
        source_pack_rel: data?.lct_device_pack_path,
        profile_pack_id: packId,
      });
      setMsg(`Draft proposal ${res.id} (${res.kind}) — Accept → Bump on Proposals`);
      setEssayOpen(false);
      navigate('/teach/proposals');
    } catch (e) {
      setError(e?.message || 'Failed to propose segmentation');
    } finally {
      setBusy(false);
    }
  };

  const gate = data?.publish_gate || {};
  const rel = gate.reliability;
  const kappa =
    gate.kappa
    ?? gate.cohen_kappa
    ?? gate.held_out_kappa
    ?? (typeof rel === 'object' ? (rel?.value ?? rel?.kappa) : rel);
  const kappaSd = gate.kappa_sd ?? gate.reliability_sd?.value;
  const allowed = gate.passed ?? gate.allowed ?? null;

  if (loading && !data) {
    return (
      <PageContainer>
        <PageHeader icon={VerifiedIcon} title="Calibration" subtitle="Prove the instrument before stakes" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="gv-calibration" />
      <Box component="main" id="gv-calibration" tabIndex={-1} aria-label="Calibration">
        <PageHeader
          icon={VerifiedIcon}
          title="Calibration"
          subtitle="Held-out expert vs engine SG/SD — summative κ gate (seeded packs stay blocked)."
          actions={(
            <Button
              size="small"
              variant="contained"
              onClick={() => navigate(`/teach/stems?tab=author&pack=${encodeURIComponent(packId)}`)}
            >
              Use in stem
            </Button>
          )}
        />
        {error && <ErrorAlert message={error} onRetry={load} />}

        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mb: 2 }} alignItems="flex-start">
          <FormControl size="small" sx={{ minWidth: 280 }}>
            <InputLabel id="cal-pack-label">Profile pack</InputLabel>
            <Select
              labelId="cal-pack-label"
              label="Profile pack"
              value={packId}
              onChange={(e) => setPackId(e.target.value)}
            >
              {profiles.map((p) => (
                <MenuItem key={p.pack_id} value={p.pack_id}>
                  {p.name || p.pack_id}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button size="small" variant="outlined" onClick={() => navigate('/teach/proposals')}>
            Proposals
          </Button>
        </Stack>

        <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap' }}>
          <Chip size="small" label={data?.profile_name || packId} />
          <Chip
            size="small"
            color={allowed === true ? 'success' : allowed === false ? 'warning' : 'default'}
            label={
              kappa != null
                ? `SG κ ${Number(kappa).toFixed(3)} · ${allowed === false ? 'gate blocked' : allowed === true ? 'gate ok' : 'gate'}`
                : (gate.detail || gate.reason || 'publish gate')
            }
          />
          {kappaSd != null && (
            <Chip size="small" variant="outlined" label={`SD κ ${Number(kappaSd).toFixed(3)}`} />
          )}
          {gate.gold_status && (
            <Chip
              size="small"
              color={gate.expert_trusted ? 'success' : 'warning'}
              variant="outlined"
              label={gate.expert_trusted ? `gold: ${gate.gold_status}` : `gold: ${gate.gold_status} (not expert)`}
            />
          )}
          <Chip size="small" label={`${data?.pair_count ?? 0} segment pairs`} variant="outlined" />
          {data?.lct_scale?.semantic_gravity?.type && (
            <Chip
              size="small"
              variant="outlined"
              label={`SG ${data.lct_scale.semantic_gravity.type}: ${(data.lct_scale.semantic_gravity.levels || []).join('/')}`}
            />
          )}
          {data?.segmentation_fidelity?.mean_f1 != null && (
            <Chip
              size="small"
              color={data.segmentation_fidelity.mean_f1 >= 0.5 ? 'success' : 'warning'}
              label={`Seg F1 ${Number(data.segmentation_fidelity.mean_f1).toFixed(2)}`}
            />
          )}
        </Stack>

        {data?.segmentation_fidelity && !data.segmentation_fidelity.error && (
          <Paper sx={{ p: 2, mb: 2 }} component="section" aria-label="Segmentation calibration" data-testid="seg-calibration">
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>Segmentation calibration</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              {data.segmentation_fidelity.note}
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
              <Chip size="small" label={`${data.segmentation_fidelity.essay_count} essays`} />
              <Chip size="small" label={`mean F1 ${data.segmentation_fidelity.mean_f1}`} />
              <Chip
                size="small"
                variant="outlined"
                label={`|Δ count| ${data.segmentation_fidelity.mean_abs_count_delta}`}
              />
            </Stack>
            <Table size="small" aria-label="Held-out essays for resegmentation">
              <TableHead>
                <TableRow>
                  <TableCell>Essay</TableCell>
                  <TableCell>F1</TableCell>
                  <TableCell>Expert segs</TableCell>
                  <TableCell>Engine segs</TableCell>
                  <TableCell>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(data.segmentation_fidelity.essays || []).map((row) => (
                  <TableRow key={row.example_id} hover selected={row.f1 < 0.6}>
                    <TableCell>
                      <Typography variant="caption">{row.example_id}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        color={row.f1 >= 0.6 ? 'success' : 'warning'}
                        label={Number(row.f1).toFixed(2)}
                      />
                    </TableCell>
                    <TableCell>{(row.expert_segments || []).length}</TableCell>
                    <TableCell>{row.engine_segment_count}</TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => openEssayResegment(row)}
                        data-testid={`resegment-essay-${row.example_id}`}
                      >
                        Resegment
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        )}
        {msg && <Alert severity="success" sx={{ mb: 2 }} role="status">{msg}</Alert>}
        {data?.segmentation_fidelity?.error && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Segmentation fidelity unavailable: {data.segmentation_fidelity.error}
          </Alert>
        )}

        {gate.expert_trusted === false && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Held-out is seeded or overlaps anchors — κ is informational only. Summative publish stays blocked until faculty expert gold (Instrument Trust B4).
            {gate.reason ? ` ${gate.reason}` : ''}
          </Alert>
        )}

        {allowed === false && gate.expert_trusted !== false && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Summative publish fails closed for this profile. Fix packs via Proposals — do not lower the bar silently.
          </Alert>
        )}

        {allowed === false && gate.expert_trusted === false && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Summative publish blocked: instrument not expert-proven yet. Do not lower κ floors to force green.
          </Alert>
        )}

        <Paper component="section" aria-labelledby="pairs-heading">
          <Typography id="pairs-heading" variant="subtitle2" sx={{ px: 1.5, pt: 1.5 }}>
            Expert vs engine (held-out)
          </Typography>
          <Table size="small" aria-label="Calibration segment pairs">
            <TableHead>
              <TableRow>
                <TableCell>Example</TableCell>
                <TableCell>Seg</TableCell>
                <TableCell>Expert SG</TableCell>
                <TableCell>Engine SG</TableCell>
                <TableCell>Expert SD</TableCell>
                <TableCell>Engine SD</TableCell>
                <TableCell>Excerpt</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(data?.segment_pairs || []).map((row, i) => {
                const mismatch = row.expert_sg && row.engine_sg && row.expert_sg !== row.engine_sg;
                return (
                  <TableRow key={`${row.example_id}-${row.segment_index}-${i}`} hover selected={mismatch}>
                    <TableCell>
                      <Typography variant="caption">{row.example_id || '—'}</Typography>
                    </TableCell>
                    <TableCell>{row.segment_index ?? '—'}</TableCell>
                    <TableCell>
                      <Chip size="small" label={row.expert_sg || '—'} color="primary" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={row.engine_sg || '—'}
                        color={mismatch ? 'warning' : 'default'}
                      />
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={row.expert_sd || '—'} variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={row.engine_sd || '—'} variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {(row.text || '').slice(0, 100)}{(row.text || '').length > 100 ? '…' : ''}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
              {!(data?.segment_pairs || []).length && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Typography color="text.secondary">
                      No held-out pairs for this profile — check device held_out.jsonl.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      </Box>

      <SystemDialog
        open={essayOpen}
        title={essay ? `Resegment · ${essay.example_id}` : 'Resegment held-out essay'}
        onClose={() => setEssayOpen(false)}
        onCancel={() => setEssayOpen(false)}
        cancelLabel="Cancel"
        width={780}
        height={620}
        actions={(
          <Button
            variant="contained"
            onClick={saveEssayResegment}
            disabled={busy || !segRationale.trim() || !segDraft?.length}
            data-testid="save-cal-resegment"
          >
            Propose segmentation_policy
          </Button>
        )}
      >
        <SegmentationEditor
          key={segKey}
          segments={essay?.expert_segments || []}
          fullText={essay?.text || ''}
          rationale={segRationale}
          onRationaleChange={setSegRationale}
          onChange={setSegDraft}
          suggestedSplits={segSuggestions}
          onRequestSuggestions={async () => {
            const full = essay?.text || '';
            const segs = segDraft || essay?.expert_segments || [];
            try {
              const res = await suggestSegmentationSplits(token, { text: full, segments: segs });
              if (res?.suggestions?.length) {
                setSegSuggestions(res.suggestions);
                return;
              }
            } catch {
              /* local fallback */
            }
            const { words, draft } = buildSegDraft(segs, full);
            setSegSuggestions(suggestSplitPoints(words, draft, 6));
          }}
        />
      </SystemDialog>
    </PageContainer>
  );
}
