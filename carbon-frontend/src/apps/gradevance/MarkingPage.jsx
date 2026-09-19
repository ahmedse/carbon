// Marking workbench — open HITL review queue → Run workbench (RULE_33).

import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Button, Chip, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import RateReviewIcon from '@mui/icons-material/RateReview';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchReviewQueue, postExpertEdit } from '../../api/gradevance';
import SkipToMain from './SkipToMain';

export default function MarkingPage() {
  const { pathname } = useLocation();
  const titlePrefix = pathname.startsWith('/teach') ? 'Teach' : 'GradeVance';
  useDocumentTitle(`${titlePrefix} · Marking`);
  const { token } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchReviewQueue(token)
      .then((data) => setRows(data.results || []))
      .catch((err) => setError(err?.message || 'Failed to load review queue'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const acceptAdvisory = async (item) => {
    try {
      await postExpertEdit(token, item.run, {
        review_item: item.id,
        edit_kind: 'other',
        before: {},
        after: { accepted: true },
        rationale: 'Marker accepted engine draft',
        resolve: true,
      });
      load();
    } catch (err) {
      setError(err?.message || 'Failed to record edit');
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={RateReviewIcon} title="Marking queue" subtitle="HITL review — every edit is a learning event" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error && !rows.length) {
    return (
      <PageContainer>
        <PageHeader icon={RateReviewIcon} title="Marking queue" subtitle="HITL review — every edit is a learning event" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="gradevance-marking" />
      <main id="gradevance-marking" tabIndex={-1} aria-label="Marking queue">
      <PageHeader
        icon={RateReviewIcon}
        title="Marking queue"
        subtitle="Open the Run workbench to edit codes/scores. ExpertEdit is append-only (RULE_32)."
      />
      {error && <ErrorAlert message={error} onRetry={load} />}
      <Paper component="section" aria-labelledby="review-queue-heading">
        <Typography
          id="review-queue-heading"
          component="h2"
          sx={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}
        >
          Open review items
        </Typography>
        <Table size="small" aria-label="HITL marking review queue">
          <caption style={{ captionSide: 'top', textAlign: 'left', padding: '8px 16px' }}>
            Open HITL review items — Open run opens the shared workbench
          </caption>
          <TableHead>
            <TableRow>
              <TableCell scope="col">Priority</TableCell>
              <TableCell scope="col">Profile</TableCell>
              <TableCell scope="col">Reason</TableCell>
              <TableCell scope="col">Status</TableCell>
              <TableCell scope="col">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{r.priority}</TableCell>
                <TableCell>{r.profile_pack_id}</TableCell>
                <TableCell>{r.reason}</TableCell>
                <TableCell><Chip size="small" label={r.status} /></TableCell>
                <TableCell>
                  <Button
                    size="small"
                    onClick={() => navigate(`/teach/runs/${r.run}`)}
                    aria-label={`Open run for ${r.profile_pack_id}`}
                  >
                    Open run
                  </Button>
                  <Button size="small" onClick={() => acceptAdvisory(r)} aria-label={`Accept advisory for ${r.profile_pack_id}`}>
                    Accept
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {!rows.length && (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography color="text.secondary">Queue empty — formative autos may skip review when confidence is high.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
      </main>
    </PageContainer>
  );
}
