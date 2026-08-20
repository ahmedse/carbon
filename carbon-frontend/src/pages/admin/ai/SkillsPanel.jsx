// src/pages/admin/ai/SkillsPanel.jsx
// Route /admin/ai/skills — W3-G UPGRADE: real skill catalog + admission
// status. Table (CarbonDataGrid) of skills with verdict chips (admitted /
// rejected — passed-flag breakdown) + usage stats (usage_count, success_rate,
// avg_latency_ms) + a detail drawer with the full admission-gate record.
// Read-only — skill admission is engine-owned. RULE_8 tokens only; RULE_10
// apiFetch only (via src/api/aiCatalog.js); RULE_16 grounded states.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  IconButton,
  Paper,
  Stack,
  Typography,
  useTheme,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import RefreshIcon from '@mui/icons-material/Refresh';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { listSkills } from '../../../api/aiCatalog';

/** Admission verdict → theme token (RULE_8). */
function verdictColor(verdict, theme) {
  if (verdict === 'admitted') return theme.palette.success.main;
  if (verdict === 'rejected') return theme.palette.error.main;
  return theme.palette.text.disabled;
}

/** "73%" / "412 ms" style formatting for usage stats. */
function pct(value) {
  if (value === null || value === undefined) return '—';
  return `${Math.round(value * 100)}%`;
}

function formatLatency(value) {
  if (value === null || value === undefined) return '—';
  return `${value} ms`;
}

export default function SkillsPanel() {
  useDocumentTitle('Skills Catalog');
  const theme = useTheme();
  const { token } = useAuth();

  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listSkills(token);
      setSkills(Array.isArray(rows) ? rows : []);
      setOffline(false);
    } catch {
      setSkills([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const columns = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Skill',
        flex: 1,
        minWidth: 160,
      },
      {
        field: 'kind',
        headerName: 'Kind',
        width: 130,
      },
      {
        field: 'verdict',
        headerName: 'Admission',
        width: 120,
        valueGetter: (_value, row) => row?.admission?.verdict ?? 'pending',
        renderCell: ({ value }) => (
          <Chip
            size="small"
            label={value === 'admitted' ? 'admitted' : value === 'rejected' ? 'rejected' : 'pending'}
            variant="outlined"
            sx={{
              fontSize: '0.625rem',
              height: 18,
              color: verdictColor(value, theme),
              borderColor: verdictColor(value, theme),
              '& .MuiChip-label': { px: 0.75 },
            }}
          />
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 110,
      },
      {
        field: 'usage_count',
        headerName: 'Uses',
        width: 80,
      },
      {
        field: 'success_rate',
        headerName: 'Success',
        width: 90,
        valueFormatter: (value) => pct(value),
      },
      {
        field: 'avg_latency_ms',
        headerName: 'Avg latency',
        width: 110,
        valueFormatter: (value) => formatLatency(value),
      },
    ],
    [theme],
  );

  const admission = selected?.admission;
  const gateFlags = admission
    ? [
        { label: 'Structural', passed: admission.structural_passed },
        { label: 'Harmlessness', passed: admission.harmlessness_passed },
        { label: 'Consistency', passed: admission.consistency_passed },
        { label: 'Marginal gain', passed: admission.marginal_gain_passed },
      ]
    : [];

  const signature = selected?.signature ?? {};

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ width: '100%', maxWidth: 1200 }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 700, flex: 1 }}>
            Skills Catalog
          </Typography>
          <Button
            size="small"
            startIcon={<RefreshIcon sx={{ fontSize: 15 }} />}
            onClick={load}
            disabled={loading}
            sx={{ fontSize: '0.75rem' }}
          >
            Refresh
          </Button>
        </Stack>

        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          Admitted skills and their admission-gate verdicts (structural / harmlessness /
          consistency / marginal gain). Read-only — admission is engine-owned.
        </Typography>

        {loading && (
          <Paper variant="outlined" sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <CircularProgress size={28} />
          </Paper>
        )}

        {!loading && offline && (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Stack spacing={1} alignItems="flex-start">
              <Stack direction="row" spacing={1} alignItems="center">
                <CloudOffIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.8125rem' }}>
                  Skill catalog unavailable
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                Could not reach the catalog service. Check the API and try again.
              </Typography>
              <Button size="small" startIcon={<RefreshIcon sx={{ fontSize: 15 }} />} onClick={load}>
                Retry
              </Button>
            </Stack>
          </Paper>
        )}

        {!loading && !offline && (
          <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
            <CarbonDataGrid
              columns={columns}
              rows={skills}
              loading={false}
              getRowId={(row) => row.id}
              pageSize={10}
              pageSizeOptions={[10, 25, 50]}
              density="compact"
              emptyMessage="No skills admitted yet."
              onRowClick={(params) => setSelected(params.row)}
            />
          </Paper>
        )}

        {/* ── Detail drawer: full admission record ───────────────────────── */}
        <Drawer
          anchor="right"
          open={Boolean(selected)}
          onClose={() => setSelected(null)}
          PaperProps={{ sx: { width: { xs: '100%', sm: 520 }, p: 2.5 } }}
        >
          {selected && (
            <Stack spacing={1}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography sx={{ fontSize: '1rem', fontWeight: 700, flex: 1 }}>
                  {selected.name}
                </Typography>
                <IconButton size="small" onClick={() => setSelected(null)} aria-label="Close detail">
                  <CloseIcon />
                </IconButton>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                <Chip size="small" label={selected.kind} sx={{ fontSize: '0.625rem', height: 18 }} />
                <Chip size="small" label={selected.status} sx={{ fontSize: '0.625rem', height: 18 }} />
                {admission && (
                  <Chip
                    size="small"
                    label={admission.verdict}
                    variant="outlined"
                    sx={{
                      fontSize: '0.625rem',
                      height: 18,
                      color: verdictColor(admission.verdict, theme),
                      borderColor: verdictColor(admission.verdict, theme),
                      '& .MuiChip-label': { px: 0.75 },
                    }}
                  />
                )}
              </Stack>

              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                {selected.description || 'No description.'}
              </Typography>

              <Divider />

              <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', rowGap: 0.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  Uses: <strong>{selected.usage_count ?? '—'}</strong>
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  Success: <strong>{pct(selected.success_rate)}</strong>
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  Avg latency: <strong>{formatLatency(selected.avg_latency_ms)}</strong>
                </Typography>
              </Stack>

              <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                Admission gate
              </Typography>
              {gateFlags.length ? (
                <Stack spacing={0.5}>
                  {gateFlags.map((g) => (
                    <Stack key={g.label} direction="row" alignItems="center" spacing={1}>
                      <Typography variant="caption" sx={{ fontSize: '0.6875rem', flex: 1 }}>
                        {g.label}
                      </Typography>
                      <Chip
                        size="small"
                        label={g.passed ? 'passed' : 'failed'}
                        variant="outlined"
                        sx={{
                          fontSize: '0.5625rem',
                          height: 16,
                          color: g.passed ? theme.palette.success.main : theme.palette.error.main,
                          borderColor: g.passed ? theme.palette.success.main : theme.palette.error.main,
                          '& .MuiChip-label': { px: 0.75 },
                        }}
                      />
                    </Stack>
                  ))}
                  <Divider sx={{ my: 0.5 }} />
                  <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', rowGap: 0.5 }}>
                    {admission.admitted_by && (
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                        Admitted by: <strong>{admission.admitted_by}</strong>
                      </Typography>
                    )}
                    {admission.rejected_by && (
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                        Rejected by: <strong>{admission.rejected_by}</strong>
                      </Typography>
                    )}
                    {admission.created_at && (
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                        Gate ran: <strong>{new Date(admission.created_at).toLocaleString()}</strong>
                      </Typography>
                    )}
                  </Stack>
                </Stack>
              ) : (
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  No admission record yet — pending engine review.
                </Typography>
              )}

              {Object.keys(signature).length > 0 && (
                <>
                  <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                    Signature
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem', overflowWrap: 'anywhere' }}>
                    {JSON.stringify(signature)}
                  </Typography>
                </>
              )}
            </Stack>
          )}
        </Drawer>
      </Stack>
    </PageContainer>
  );
}
