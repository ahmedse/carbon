// Accessibility checklist — WCAG toward VPAT (Phase D).

import React, { useCallback, useEffect, useState } from 'react';
import {
  Box, Chip, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import AccessibilityNewIcon from '@mui/icons-material/AccessibilityNew';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchAccessibility } from '../../api/gradevance';
import SkipToMain from './SkipToMain';

function statusColor(status) {
  switch ((status || '').toLowerCase()) {
    case 'pass': return 'success';
    case 'partial': return 'warning';
    case 'fail': return 'error';
    case 'pending': return 'default';
    default: return 'default';
  }
}

export default function AccessibilityPage() {
  useDocumentTitle('GradeVance · Accessibility');
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchAccessibility(token)
      .then(setData)
      .catch((err) => setError(err?.message || 'Failed to load accessibility checklist'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={AccessibilityNewIcon} title="Accessibility" subtitle="WCAG checklist toward VPAT" />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error && !data) {
    return (
      <PageContainer>
        <PageHeader icon={AccessibilityNewIcon} title="Accessibility" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  const items = data?.items || data?.criteria || [];
  const counts = data?.counts || {};

  return (
    <PageContainer>
      <SkipToMain targetId="gv-accessibility" />
      <Box component="main" id="gv-accessibility" tabIndex={-1} aria-label="Accessibility checklist">
        <PageHeader
          icon={AccessibilityNewIcon}
          title="Accessibility"
          subtitle={data?.standard || 'WCAG 2.2 AA toward VPAT'}
        />

        {error && <ErrorAlert message={error} onRetry={load} />}

        <StackChips counts={counts} />

        {data?.note && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            {data.note}
          </Typography>
        )}

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          Primary surfaces: /learn · /teach · /apps/gradevance
        </Typography>

        {items.length === 0 ? (
          <EmptyState
            icon={<AccessibilityNewIcon />}
            title="No checklist items"
            description="Accessibility API returned an empty checklist."
          />
        ) : (
          <Paper component="section" aria-label="WCAG checklist">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Criterion</TableCell>
                  <TableCell>Surface</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((row) => (
                  <TableRow key={row.criterion || row.id || row.name}>
                    <TableCell>{row.criterion || row.name || row.id}</TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {row.surface || row.evidence || '—'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={row.status || '—'} color={statusColor(row.status)} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        )}
      </Box>
    </PageContainer>
  );
}

function StackChips({ counts }) {
  const entries = Object.entries(counts || {});
  if (!entries.length) return null;
  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1.5 }} aria-label="Status counts">
      {entries.map(([k, v]) => (
        <Chip key={k} size="small" label={`${k}: ${v}`} color={statusColor(k)} />
      ))}
    </Box>
  );
}
