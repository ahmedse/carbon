// Progress — wave and band trajectory grouped by assignment (Phase D / L4).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, Paper, Stack, Typography,
} from '@mui/material';
import TimelineIcon from '@mui/icons-material/Timeline';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchMyProgress } from '../../api/gradevance';
import SkipToMain from '../../components/gradevance/SkipToMain';
import WaveChart from '../../components/gradevance/WaveChart';
import LearnReadingWidth, { useLearnPrimarySize } from '../../components/gradevance/LearnReadingWidth';
import { criterionLabel, statusChipColor, statusLabel } from './learnCopy';

function displayableBandEntries(bands) {
  if (!bands || typeof bands !== 'object' || bands.withheld === true) return [];
  return Object.entries(bands).filter(([k, v]) => k !== 'withheld' && v != null && typeof v !== 'object');
}

function groupByAssignment(rows) {
  const map = new Map();
  for (const row of rows) {
    const key = String(row.assignment_id || row.assignment || row.title || 'unknown');
    if (!map.has(key)) {
      map.set(key, {
        assignment_id: row.assignment_id || row.assignment,
        title: row.title || `Assignment ${key}`,
        runs: [],
      });
    }
    map.get(key).runs.push(row);
  }
  for (const g of map.values()) {
    g.runs.sort((a, b) => {
      const ta = a.created_at || '';
      const tb = b.created_at || '';
      return ta.localeCompare(tb);
    });
  }
  return Array.from(map.values());
}

export default function ProgressPage() {
  useDocumentTitle('Learn · Progress');
  const { token } = useAuth();
  const navigate = useNavigate();
  const primarySize = useLearnPrimarySize();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchMyProgress(token)
      .then((data) => setRows(data.results || data || []))
      .catch((err) => setError(err?.message || 'Failed to load progress'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const groups = useMemo(() => groupByAssignment(rows), [rows]);
  const showsLetterBands = useMemo(
    () => rows.some((r) => displayableBandEntries(r.advisory_bands).length > 0),
    [rows],
  );

  if (loading) {
    return (
      <PageContainer>
        <LearnReadingWidth>
          <PageHeader icon={TimelineIcon} title="Progress" subtitle="Your wave and band trajectory" />
          <LoadingSkeleton variant="console" />
        </LearnReadingWidth>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <LearnReadingWidth>
          <PageHeader icon={TimelineIcon} title="Progress" />
          <ErrorAlert message={error} onRetry={load} />
        </LearnReadingWidth>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <SkipToMain targetId="learn-progress" />
      <LearnReadingWidth>
        <Box component="main" id="learn-progress" tabIndex={-1} aria-label="My progress">
          <PageHeader
            icon={TimelineIcon}
            title="Progress"
            subtitle="Wave and band trajectory by assignment."
            actions={(
              <Button
                size={primarySize}
                variant="outlined"
                onClick={() => navigate('/learn/assignments')}
                sx={{ minHeight: primarySize === 'medium' ? 40 : undefined }}
              >
                My assignments
              </Button>
            )}
          />

          {showsLetterBands && (
            <Alert severity="warning" sx={{ mb: 2 }} role="status">
              Advisory only — letter bands on this page are formative coaching signals, not final grades.
              Summative marks stay withheld until a marker releases them.
            </Alert>
          )}

          {groups.length === 0 ? (
            <EmptyState
              icon={<TimelineIcon />}
              title="No progress yet"
              description="Open an assignment to draft and get coaching — your wave will appear here."
              actionLabel="My assignments"
              onAction={() => navigate('/learn/assignments')}
            />
          ) : (
            <Stack spacing={2} role="list" aria-label="Progress by assignment">
              {groups.map((group) => {
                const asgId = group.assignment_id;
                const latest = group.runs[group.runs.length - 1];
                const trajectoryPoints = group.runs.flatMap((r, idx) => {
                  const pts = r.wave_points || r.wave?.points || [];
                  if (!pts.length) return [];
                  // Offset each run's wave so the trajectory reads left-to-right over time.
                  const base = idx * 1000;
                  return pts.map((p) => ({
                    ...p,
                    word_offset: (p.word_offset ?? 0) + base,
                  }));
                });
                return (
                  <Paper
                    key={asgId || group.title}
                    variant="outlined"
                    role="listitem"
                    sx={{ p: 1.5 }}
                  >
                    <Stack spacing={1.25}>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Typography variant="body2" sx={{ flex: 1, minWidth: 140, fontWeight: 600 }}>
                          {group.title}
                        </Typography>
                        <Chip
                          size="small"
                          label={`${group.runs.length} draft${group.runs.length === 1 ? '' : 's'}`}
                          variant="outlined"
                        />
                        {latest && (
                          <Chip
                            size="small"
                            label={statusLabel(latest.status || (latest.released ? 'released' : 'draft'))}
                            color={statusChipColor(latest.status || (latest.released ? 'released' : 'draft'))}
                          />
                        )}
                      </Stack>

                      <Stack spacing={1} aria-label="Submission trajectory">
                        {group.runs.map((row) => {
                          const bandEntries = displayableBandEntries(row.advisory_bands);
                          const when = row.created_at || row.updated_at;
                          return (
                            <Box
                              key={row.run_id || row.submission_id || `${asgId}-${when}`}
                              sx={{ pl: 1, borderLeft: 2, borderColor: 'divider' }}
                            >
                              <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                                {when && (
                                  <Typography variant="caption" color="text.secondary">
                                    {new Date(when).toLocaleString()}
                                  </Typography>
                                )}
                                <Chip
                                  size="small"
                                  label={statusLabel(row.status || (row.released ? 'released' : 'draft'))}
                                  color={statusChipColor(row.status || (row.released ? 'released' : 'draft'))}
                                />
                              </Stack>
                              {bandEntries.length > 0 && (
                                <Stack
                                  direction="row"
                                  spacing={0.75}
                                  flexWrap="wrap"
                                  useFlexGap
                                  sx={{ mt: 0.5 }}
                                  aria-label="Advisory bands"
                                >
                                  {bandEntries.map(([k, v]) => (
                                    <Chip
                                      key={k}
                                      size="small"
                                      label={`${criterionLabel(k)}: ${v}`}
                                      variant="outlined"
                                    />
                                  ))}
                                </Stack>
                              )}
                            </Box>
                          );
                        })}
                      </Stack>

                      {trajectoryPoints.length > 0 && (
                        <Box aria-label="Semantic wave trajectory across drafts">
                          <Typography variant="caption" color="text.secondary">
                            Wave trajectory (earliest → latest draft)
                          </Typography>
                          <WaveChart points={trajectoryPoints} />
                        </Box>
                      )}

                      {asgId && (
                        <Box>
                          <Button
                            size={primarySize}
                            onClick={() => navigate(`/learn/assignments/${asgId}`)}
                            sx={{ minHeight: primarySize === 'medium' ? 40 : undefined }}
                          >
                            Open assignment
                          </Button>
                        </Box>
                      )}
                    </Stack>
                  </Paper>
                );
              })}
            </Stack>
          )}
        </Box>
      </LearnReadingWidth>
    </PageContainer>
  );
}
