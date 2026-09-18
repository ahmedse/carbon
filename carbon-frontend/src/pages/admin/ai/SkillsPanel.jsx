// src/pages/admin/ai/SkillsPanel.jsx
// Route /admin/ai/skills — skill catalog + admission status + admin
// promote/reject decisions (PEC-6B). Reused by AIWorkspace Console Skills
// tab (single source of truth — no duplicate panel).
//
// CBAC: promote/reject require ai:publisher | ai:process_owner. The backend
// is the authority — we disable + tooltip missing caps and lock on 403.
// RULE_8 tokens only; RULE_10 apiFetch only; RULE_23 outcome copy only.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Drawer,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
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
import { useNotification } from '../../../components/NotificationProvider';
import { AI_PROCESS_OWNER, AI_PUBLISHER, hasAnyCap } from '../../../capabilities';
import { listSkills, promoteSkill, rejectSkill } from '../../../api/aiCatalog';
import { getCommandCenter } from '../../../api/aiControlPlane';

/** Admission verdict → theme token (RULE_8). */
function verdictColor(verdict, theme) {
  if (verdict === 'admitted') return theme.palette.success.main;
  if (verdict === 'rejected') return theme.palette.error.main;
  return theme.palette.text.disabled;
}

/** Status → outcome label (RULE_23 — never engine tokens). */
export function statusLabel(status) {
  if (status === 'instance_promoted') return 'Promoted';
  if (status === 'user_approved') return 'Approved';
  if (status === 'deprecated') return 'Retired';
  if (status === 'draft') return 'Draft';
  return status || '—';
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

export function capabilityKeys(caps) {
  if (!Array.isArray(caps)) return [];
  return caps
    .map((c) =>
      typeof c === 'string' ? c : c?.key || c?.capability || c?.code || ''
    )
    .filter(Boolean);
}

/** Button disabled + tooltipped when the caller lacks a capability. */
function GatedButton({ allowed, reason, children, ...props }) {
  const button = (
    <Button {...props} disabled={props.disabled || !allowed}>
      {children}
    </Button>
  );
  if (!allowed) {
    return (
      <Tooltip title={reason}>
        <span>{button}</span>
      </Tooltip>
    );
  }
  return button;
}

const PROMOTE_STATUSES = new Set(['draft', 'user_approved']);
const REJECT_STATUSES = new Set(['draft', 'user_approved', 'instance_promoted']);

export default function SkillsPanel() {
  useDocumentTitle('Skills Catalog');
  const theme = useTheme();
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const caps = useMemo(() => capabilityKeys(userCapabilities), [userCapabilities]);
  const canDecide = useMemo(
    () => hasAnyCap(caps, [AI_PUBLISHER, AI_PROCESS_OWNER]),
    [caps],
  );

  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [selected, setSelected] = useState(null);
  const [acting, setActing] = useState('');
  const [denied, setDenied] = useState({});
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [learningFrozen, setLearningFrozen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, command] = await Promise.all([
        listSkills(token),
        getCommandCenter(token).catch(() => null),
      ]);
      const frozen = Boolean(
        command?.containment?.learning_admissions_frozen
          || ['learning_freeze', 'full_stop'].includes(
            command?.containment?.containment_level,
          ),
      );
      setLearningFrozen(frozen);
      setSkills(Array.isArray(rows) ? rows : []);
      setOffline(false);
      setSelected((prev) => {
        if (!prev) return null;
        const next = (Array.isArray(rows) ? rows : []).find((r) => r.id === prev.id);
        return next || null;
      });
    } catch {
      setSkills([]);
      setOffline(true);
      setLearningFrozen(false);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const skillDenied = selected?.id ? Boolean(denied[selected.id]) : false;
  const status = selected?.status || '';
  const canPromote =
    canDecide
    && !skillDenied
    && !learningFrozen
    && PROMOTE_STATUSES.has(status)
    && acting !== 'promote';
  const canReject =
    canDecide && !skillDenied && REJECT_STATUSES.has(status) && acting !== 'reject';

  const promoteReason = learningFrozen
    ? 'Learning admissions are frozen — promote is locked.'
    : skillDenied
      ? 'You do not have permission for this action.'
      : !canDecide
        ? 'Requires ai:publisher or ai:process_owner'
        : !PROMOTE_STATUSES.has(status)
          ? 'Only draft or approved skills can be promoted.'
          : '';

  const rejectReasonTip = skillDenied
    ? 'You do not have permission for this action.'
    : !canDecide
      ? 'Requires ai:publisher or ai:process_owner'
      : !REJECT_STATUSES.has(status)
        ? 'This skill is already retired.'
        : '';

  const doPromote = async () => {
    if (!selected?.id) return;
    setActing('promote');
    try {
      await promoteSkill(token, selected.id);
      notify({ message: `Promoted “${selected.name}”.`, type: 'success' });
      await load();
    } catch (err) {
      if (err?.status === 403) {
        setDenied((prev) => ({ ...prev, [selected.id]: true }));
        notify({ message: "You don't have permission for this action.", type: 'warning' });
      } else {
        notifyFromError(err, 'Could not promote skill');
      }
    } finally {
      setActing('');
    }
  };

  const doReject = async () => {
    if (!selected?.id) return;
    setActing('reject');
    try {
      await rejectSkill(token, selected.id, rejectReason.trim());
      notify({ message: `Retired “${selected.name}”.`, type: 'success' });
      setRejectOpen(false);
      setRejectReason('');
      await load();
    } catch (err) {
      if (err?.status === 403) {
        setDenied((prev) => ({ ...prev, [selected.id]: true }));
        setRejectOpen(false);
        notify({ message: "You don't have permission for this action.", type: 'warning' });
      } else {
        notifyFromError(err, 'Could not retire skill');
      }
    } finally {
      setActing('');
    }
  };

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
        valueFormatter: (value) => statusLabel(value),
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
  const showActions = selected && status !== 'deprecated';

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ width: '100%', maxWidth: 1200 }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 700, flex: 1 }}>
            Skills Catalog
          </Typography>
          <Button
            size="small"
            startIcon={<RefreshIcon sx={{ fontSize: '0.9375rem' }} />}
            onClick={load}
            disabled={loading}
            sx={{ fontSize: '0.75rem' }}
          >
            Refresh
          </Button>
        </Stack>

        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          Skill catalog with admission-gate verdicts. Publishers and process owners can
          promote a skill after the gate admits it, or retire one with a reason.
        </Typography>

        {learningFrozen && (
          <Alert severity="warning" data-testid="skills-learning-freeze">
            Learning admissions are frozen. Promote is disabled until containment returns
            to normal.
          </Alert>
        )}

        {loading && (
          <Paper variant="outlined" sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <CircularProgress size={28} />
          </Paper>
        )}

        {!loading && offline && (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Stack spacing={1} alignItems="flex-start">
              <Stack direction="row" spacing={1} alignItems="center">
                <CloudOffIcon sx={{ fontSize: '1.125rem', color: 'text.secondary' }} />
                <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.8125rem' }}>
                  Skill catalog unavailable
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                Could not reach the catalog service. Check the API and try again.
              </Typography>
              <Button size="small" startIcon={<RefreshIcon sx={{ fontSize: '0.9375rem' }} />} onClick={load}>
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
              emptyMessage="No skills in the catalog yet."
              onRowClick={(params) => setSelected(params.row)}
            />
          </Paper>
        )}

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
                <Chip
                  size="small"
                  label={statusLabel(selected.status)}
                  sx={{ fontSize: '0.625rem', height: 18 }}
                />
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

              {showActions && (
                <>
                  <Divider />
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <GatedButton
                      allowed={canPromote}
                      reason={promoteReason}
                      size="small"
                      variant="contained"
                      onClick={doPromote}
                      disabled={Boolean(acting)}
                      data-testid="skill-promote"
                    >
                      {acting === 'promote' ? 'Promoting…' : 'Promote'}
                    </GatedButton>
                    <GatedButton
                      allowed={canReject}
                      reason={rejectReasonTip}
                      size="small"
                      variant="outlined"
                      color="error"
                      onClick={() => {
                        setRejectReason('');
                        setRejectOpen(true);
                      }}
                      disabled={Boolean(acting)}
                      data-testid="skill-reject"
                    >
                      Retire
                    </GatedButton>
                  </Stack>
                </>
              )}

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
                  No admission record yet — pending review.
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

        <Dialog
          open={rejectOpen}
          onClose={() => !acting && setRejectOpen(false)}
          maxWidth="xs"
          fullWidth
        >
          <DialogTitle sx={{ fontSize: '0.9375rem', fontWeight: 600 }}>
            Retire skill?
          </DialogTitle>
          <DialogContent>
            <DialogContentText sx={{ fontSize: '0.8125rem', mb: 1.5 }}>
              “{selected?.name}” will leave the active catalog. You can add an optional reason.
            </DialogContentText>
            <TextField
              autoFocus
              fullWidth
              size="small"
              multiline
              minRows={2}
              label="Reason (optional)"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              inputProps={{ maxLength: 2000, 'data-testid': 'skill-reject-reason' }}
            />
          </DialogContent>
          <DialogActions sx={{ px: 2, pb: 1.5 }}>
            <Button size="small" onClick={() => setRejectOpen(false)} disabled={Boolean(acting)}>
              Cancel
            </Button>
            <Button
              size="small"
              color="error"
              variant="contained"
              onClick={doReject}
              disabled={Boolean(acting)}
              data-testid="skill-reject-confirm"
            >
              {acting === 'reject' ? 'Retiring…' : 'Retire'}
            </Button>
          </DialogActions>
        </Dialog>
      </Stack>
    </PageContainer>
  );
}
