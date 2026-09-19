// Learning proposals — HITL intelligence promotion queue (P2).

import React, { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Box, Button, Chip, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  bumpProposal, decideProposal, fetchProposals, repinProposal,
} from '../../api/gradevance';
import SkipToMain from './SkipToMain';

export default function ProposalsPage() {
  const { pathname } = useLocation();
  const titlePrefix = pathname.startsWith('/teach') ? 'Teach' : 'GradeVance';
  useDocumentTitle(`${titlePrefix} · Proposals`);
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchProposals(token)
      .then((data) => setRows(data.results || []))
      .catch((err) => setError(err?.message || 'Failed to load proposals'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (id, decision) => {
    setError(null);
    try {
      await decideProposal(token, id, decision);
      load();
    } catch (err) {
      setError(err?.message || 'Decision failed');
    }
  };

  const bump = async (id) => {
    setError(null);
    setInfo(null);
    try {
      const result = await bumpProposal(token, id, { require_canary: false });
      if (result.bump_kind === 'segmentation_policy' || result.markers_added) {
        const n = (result.markers_added || []).length;
        setInfo(
          `Segmentation bump → ${result.dest_rel}`
          + (n ? ` (+${n} markers)` : '')
          + ' — re-pin profile for NEW runs only',
        );
      } else {
        setInfo(`Pack bump → ${result.dest_rel} (anchor ${result.anchor_id})`);
      }
      load();
    } catch (err) {
      setError(err?.message || 'Bump failed');
    }
  };

  const repin = async (id) => {
    setError(null);
    setInfo(null);
    try {
      const result = await repinProposal(token, id, {
        base_profile_id: 'naa_cycle1_exam_prep',
        update_draft_assignments: true,
      });
      setInfo(
        `Re-pinned profile ${result.profile_pack_id}@v${result.profile_version} · `
        + `draft assignments updated: ${(result.draft_assignments_updated || []).length}`,
      );
      load();
    } catch (err) {
      setError(err?.message || 'Repin failed');
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={LightbulbIcon} title="Intelligence proposals" subtitle="ExpertEdit → ProposalMiner → governed activate" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="gradevance-proposals" />
      <Box component="main" id="gradevance-proposals" tabIndex={-1} aria-label="Intelligence proposals">
      <PageHeader
        icon={LightbulbIcon}
        title="Intelligence proposals"
        subtitle="Accept → bump device pack → re-pin profile. Never silent cohort rewrite."
      />
      {error && <ErrorAlert message={error} onRetry={load} />}
      {info && (
        <Typography variant="body2" color="success.main" sx={{ mb: 1 }} role="status">{info}</Typography>
      )}
      <Typography component="h2" variant="h6" sx={{ mb: 1 }} id="proposals-queue-heading">
        Proposal queue
      </Typography>
      <Paper component="section" aria-labelledby="proposals-queue-heading">
        <Table size="small" aria-label="Engine intelligence proposals">
          <caption style={{ captionSide: 'top', textAlign: 'left', padding: '8px 16px' }}>
            ExpertEdit clusters awaiting governed activation
          </caption>
          <TableHead>
            <TableRow>
              <TableCell scope="col">Kind</TableCell>
              <TableCell scope="col">Status</TableCell>
              <TableCell scope="col">Cluster</TableCell>
              <TableCell scope="col">Edits</TableCell>
              <TableCell scope="col">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{r.kind}</TableCell>
                <TableCell><Chip size="small" label={r.status} /></TableCell>
                <TableCell>
                  <Typography variant="caption">{JSON.stringify(r.payload?.cluster_key || {})}</Typography>
                  {r.payload?.pack_bump?.dest_rel && (
                    <Typography variant="caption" display="block" color="text.secondary">
                      bump: {r.payload.pack_bump.dest_rel}
                    </Typography>
                  )}
                  {r.payload?.profile_repin?.profile_pack_id && (
                    <Typography variant="caption" display="block" color="text.secondary">
                      profile: {r.payload.profile_repin.profile_pack_id}@v{r.payload.profile_repin.profile_version}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>{r.payload?.edit_count ?? (r.source_edit_ids || []).length}</TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    <Button size="small" onClick={() => decide(r.id, 'propose')}>Propose</Button>
                    <Button size="small" color="success" onClick={() => decide(r.id, 'accept')}>Accept</Button>
                    <Button size="small" color="inherit" onClick={() => decide(r.id, 'reject')}>Reject</Button>
                    {r.status === 'accepted'
                      && (r.kind === 'anchor' || r.kind === 'segmentation_policy')
                      && !r.payload?.pack_bump && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => bump(r.id)}
                        data-testid={`bump-proposal-${r.id}`}
                      >
                        {r.kind === 'segmentation_policy' ? 'Bump segmentation' : 'Bump pack'}
                      </Button>
                    )}
                    {r.payload?.pack_bump && !r.payload?.profile_repin && (
                      <Button size="small" variant="contained" onClick={() => repin(r.id)}>Re-pin profile</Button>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {!rows.length && (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography color="text.secondary">No proposals yet — marker LCT/rubric edits will mine drafts.</Typography>
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
