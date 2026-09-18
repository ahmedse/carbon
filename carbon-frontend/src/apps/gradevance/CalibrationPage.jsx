// Calibration — held-out expert vs engine + κ (prove the instrument).

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem, Paper, Select,
  Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import VerifiedIcon from '@mui/icons-material/Verified';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchCalibration, fetchProfiles } from '../../api/gradevance';
import SkipToMain from './SkipToMain';

export default function CalibrationPage() {
  useDocumentTitle('GradeVance · Calibration');
  const { token } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const [profiles, setProfiles] = useState([]);
  const [packId, setPackId] = useState(params.get('profile_pack_id') || 'naa_cycle1_exam_prep');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  const gate = data?.publish_gate || {};
  const rel = gate.reliability;
  const kappa =
    gate.kappa
    ?? gate.cohen_kappa
    ?? gate.held_out_kappa
    ?? (typeof rel === 'object' ? rel?.kappa : rel);
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
          subtitle="Held-out expert vs engine SG — κ gate before summative publish."
          actions={(
            <Button
              size="small"
              variant="contained"
              onClick={() => navigate(`/apps/gradevance/courses?pack=${encodeURIComponent(packId)}`)}
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
          <Button size="small" variant="outlined" onClick={() => navigate('/apps/gradevance/proposals')}>
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
                ? `κ ${Number(kappa).toFixed(3)} · ${allowed === false ? 'gate blocked' : allowed === true ? 'gate ok' : 'gate'}`
                : (gate.detail || gate.reason || 'publish gate')
            }
          />
          <Chip size="small" label={`${data?.pair_count ?? 0} segment pairs`} variant="outlined" />
        </Stack>

        {allowed === false && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Summative publish fails closed for this profile. Fix packs via Proposals — do not lower the bar silently.
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
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>{row.expert_sd || '—'}</TableCell>
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
                  <TableCell colSpan={6}>
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
    </PageContainer>
  );
}
