/** Ops Canvas Job Map host — ADR-0041 Agent-first execution board; ADR-0043 V5 Operator story. */
import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  Divider,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MapOutlinedIcon from '@mui/icons-material/MapOutlined';
import { humanizeCanvasText, humanStatusLabel } from '../utils/humanizeCanvas';

const STATUS_COLOR = {
  completed: 'success',
  done: 'success',
  complete: 'success',
  running: 'primary',
  pending: 'default',
  planned: 'default',
  blocked: 'warning',
  awaiting_approval: 'warning',
  failed: 'error',
  skipped: 'default',
  partial: 'warning',
};

function LayerCard({ title, children, muted, accent }) {
  return (
    <Box
      sx={{
        border: 1,
        borderColor: accent ? 'primary.main' : 'divider',
        borderRadius: 1,
        p: 1.25,
        bgcolor: muted ? 'action.hover' : 'background.paper',
      }}
    >
      <Typography
        variant="caption"
        sx={{
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          color: accent ? 'primary.main' : 'text.secondary',
          display: 'block',
          mb: 0.75,
        }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  );
}

LayerCard.propTypes = {
  title: PropTypes.string.isRequired,
  children: PropTypes.node,
  muted: PropTypes.bool,
  accent: PropTypes.bool,
};

function layerTitles(operatorSimple, isAgent) {
  if (operatorSimple) {
    return {
      intent: 'Goal',
      live: 'Where we are',
      jobMap: 'The path',
      evidence: 'What we found',
      outcome: 'Outcome',
    };
  }
  return {
    intent: 'Intent',
    live: 'Live run · execution',
    jobMap: isAgent ? 'Job map · plan steps' : 'Job map',
    evidence: isAgent ? 'Evidence · outputs' : 'Evidence',
    outcome: 'Outcome',
  };
}

function displayText(text, operatorSimple) {
  const raw = text == null ? '' : String(text);
  return operatorSimple ? humanizeCanvasText(raw) : raw;
}

function formatConsentCopy(pending, operatorSimple) {
  if (!pending) return '';
  let msg = 'Consent pending';
  if (pending.tool) msg += `: ${pending.tool}`;
  if (pending.intent) msg += ` — ${pending.intent}`;
  if (!pending.tool && !pending.intent && typeof pending !== 'object') {
    msg += `: ${String(pending)}`;
  }
  return operatorSimple ? humanizeCanvasText(msg) : msg;
}

function QosChipCluster({ qos }) {
  if (!qos || typeof qos !== 'object') return null;
  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
      {qos.acceptance_status && (
        <Chip size="small" label={`QoS ${qos.acceptance_status}`} color="primary" variant="outlined" />
      )}
      {qos.requirements_total != null && (
        <Chip
          size="small"
          variant="outlined"
          label={`${qos.requirements_met ?? 0}/${qos.requirements_total} met`}
        />
      )}
      {(qos.requirements_partial || 0) > 0 && (
        <Chip size="small" color="warning" variant="outlined" label={`${qos.requirements_partial} partial`} />
      )}
      {(qos.requirements_missed || 0) > 0 && (
        <Chip size="small" color="error" variant="outlined" label={`${qos.requirements_missed} missed`} />
      )}
    </Stack>
  );
}

QosChipCluster.propTypes = {
  qos: PropTypes.object,
};

/**
 * Agent Job Map = plan + live execution + evidence + outcome.
 * Chat Job Brief = thinner advisory (Intent + Evidence) — demoted visually.
 */
export default function OpsCanvasHost({
  artifact,
  readOnly = true,
  flightQos = null,
  operatorSimple = true,
}) {
  const [qosOpen, setQosOpen] = useState(false);

  const payload = useMemo(() => {
    const raw = artifact?.content_json;
    if (!raw || typeof raw !== 'object') return null;
    if (raw.kind && raw.kind !== 'job_map') return null;
    return raw;
  }, [artifact]);

  const layers = payload?.layers || {};
  const mode = payload?.mode || 'chat';
  const isAgent = mode === 'agent';
  const related = payload?.related_object;
  const titles = layerTitles(operatorSimple, isAgent);

  if (!payload) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Not a Job Map canvas.
        </Typography>
      </Box>
    );
  }

  const intent = layers.intent || {};
  const job = layers.job_map || {};
  const live = layers.live_run || {};
  const evidence = layers.evidence || {};
  const outcome = layers.outcome || {};
  const qos = flightQos || live.qos;
  const progress = Number(live.progress_pct) || 0;
  const steps = job.steps || [];
  const liveStatus = live.status || (isAgent ? 'planned' : 'idle');
  const liveStatusLabel = operatorSimple ? humanStatusLabel(liveStatus) : liveStatus;
  const blockers = (live.blockers || []).map((b) => displayText(b, operatorSimple)).filter(Boolean);
  const consentCopy = live.pending_consent ? formatConsentCopy(live.pending_consent, operatorSimple) : '';

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }} data-testid="ops-canvas-host">
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
        <MapOutlinedIcon sx={{ fontSize: 18, color: 'primary.main' }} />
        <Typography variant="subtitle2" fontWeight={700} sx={{ flex: 1, minWidth: 120 }}>
          {artifact?.title || payload.title || (isAgent ? 'Agent Job Map' : 'Job Brief')}
        </Typography>
        <Chip
          size="small"
          label={isAgent ? 'Agent · execution' : 'Chat · advisory'}
          color={isAgent ? 'warning' : 'default'}
          variant={isAgent ? 'filled' : 'outlined'}
        />
        {!operatorSimple && payload.plan_id && (
          <Chip size="small" variant="outlined" label={`Plan ${String(payload.plan_id).slice(0, 8)}…`} />
        )}
        {isAgent && (
          <Chip
            size="small"
            color={STATUS_COLOR[liveStatus] || 'default'}
            label={liveStatusLabel}
          />
        )}
      </Stack>

      {!isAgent && (
        <Alert severity="info" sx={{ mb: 1.5, py: 0, fontSize: '0.75rem' }}>
          Chat Job Brief — read-only synthesis. Full plan / run / consent lives on Agent Job Maps.
        </Alert>
      )}

      {related?.type && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          Attached: {related.type}
          {related.id ? ` #${related.id}` : ''}
          {related.label ? ` — ${related.label}` : ''}
        </Typography>
      )}

      <Stack spacing={1.25}>
        <LayerCard title={titles.intent} muted={!isAgent}>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {displayText(intent.ask, operatorSimple) || '—'}
          </Typography>
          {intent.success_criteria ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              Success: {displayText(intent.success_criteria, operatorSimple)}
            </Typography>
          ) : null}
        </LayerCard>

        {isAgent && (
          <LayerCard title={titles.live} accent>
            <Stack spacing={0.75}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
                  {settledLabel(steps)} · {progress}%
                </Typography>
                <Chip size="small" color={STATUS_COLOR[liveStatus] || 'default'} label={liveStatusLabel} />
              </Stack>
              <LinearProgress
                variant="determinate"
                value={Math.max(0, Math.min(100, progress))}
                sx={{ height: 8, borderRadius: 1 }}
              />
              {qos && typeof qos === 'object' && (
                operatorSimple ? (
                  <Box data-testid="ops-canvas-qos-expand">
                    <Button
                      fullWidth
                      size="small"
                      onClick={() => setQosOpen((v) => !v)}
                      endIcon={qosOpen ? <ExpandLessIcon sx={{ fontSize: 16 }} /> : <ExpandMoreIcon sx={{ fontSize: 16 }} />}
                      sx={{
                        justifyContent: 'space-between',
                        textTransform: 'none',
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        px: 0.5,
                        py: 0.5,
                        color: 'text.secondary',
                      }}
                      aria-expanded={qosOpen}
                    >
                      Quality details
                    </Button>
                    <Collapse in={qosOpen} unmountOnExit>
                      <Box sx={{ pt: 0.5 }}>
                        <QosChipCluster qos={qos} />
                      </Box>
                    </Collapse>
                  </Box>
                ) : (
                  <QosChipCluster qos={qos} />
                )
              )}
              {blockers.length > 0 && (
                <Alert severity="warning" sx={{ py: 0, fontSize: '0.75rem' }}>
                  {blockers.join('; ')}
                </Alert>
              )}
              {consentCopy && (
                <Alert severity="warning" sx={{ py: 0, fontSize: '0.75rem' }}>
                  {consentCopy}
                </Alert>
              )}
            </Stack>
          </LayerCard>
        )}

        <LayerCard title={titles.jobMap} accent={isAgent}>
          {steps.length === 0 ? (
            <Typography variant="caption" color="text.secondary">No steps yet.</Typography>
          ) : (
            <Stack spacing={0.5}>
              {steps.map((s) => {
                const stepStatus = s.status || 'pending';
                const stepLabel = operatorSimple ? humanStatusLabel(stepStatus) : stepStatus;
                return (
                  <Stack key={s.id || s.title} direction="row" spacing={1} alignItems="center">
                    <Chip
                      size="small"
                      color={STATUS_COLOR[stepStatus] || 'default'}
                      label={stepLabel}
                      sx={{ minWidth: 88, fontSize: '0.65rem' }}
                    />
                    <Typography variant="body2" sx={{ flex: 1 }}>
                      {s.title}
                    </Typography>
                    {!operatorSimple && s.tool ? (
                      <Typography variant="caption" color="text.disabled">{s.tool}</Typography>
                    ) : null}
                  </Stack>
                );
              })}
            </Stack>
          )}
          {!operatorSimple && (job.tools || []).length > 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Tools: {(job.tools || []).join(', ')}
            </Typography>
          )}
          {!operatorSimple && (job.capabilities || []).length > 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              CBAC: {(job.capabilities || []).join(', ')}
            </Typography>
          )}
        </LayerCard>

        <LayerCard title={titles.evidence}>
          {evidence.headline ? (
            <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
              {displayText(evidence.headline, operatorSimple)}
            </Typography>
          ) : null}
          {evidence.prose ? (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1, whiteSpace: 'pre-wrap' }}>
              {displayText(String(evidence.prose).slice(0, 800), operatorSimple)}
            </Typography>
          ) : null}
          {(evidence.tables || []).slice(0, 3).map((tbl, idx) => (
            <Box key={idx} sx={{ mb: 1, overflow: 'auto' }}>
              <Typography variant="caption" fontWeight={600}>
                {tbl.title || `Table ${idx + 1}`}
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {(tbl.columns || tbl.headers || []).slice(0, 6).map((c) => (
                      <TableCell key={String(c)} sx={{ fontSize: '0.7rem', py: 0.25 }}>
                        {typeof c === 'object' ? c.label || c.key : String(c)}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(tbl.rows || []).slice(0, 8).map((row, ri) => (
                    <TableRow key={ri}>
                      {(Array.isArray(row) ? row : Object.values(row || {})).slice(0, 6).map((cell, ci) => (
                        <TableCell key={ci} sx={{ fontSize: '0.7rem', py: 0.25 }}>
                          {cell == null ? '—' : String(cell)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          ))}
          {(evidence.caveats || []).length > 0 && (
            <Typography variant="caption" color="warning.main" display="block">
              Caveats:{' '}
              {(evidence.caveats || [])
                .map((c) => displayText(typeof c === 'string' ? c : c.text || '', operatorSimple))
                .join('; ')}
            </Typography>
          )}
          {!evidence.headline && !(evidence.tables || []).length && (
            <Typography variant="caption" color="text.secondary">
              {isAgent ? 'Outputs appear as steps complete.' : 'No evidence yet.'}
            </Typography>
          )}
        </LayerCard>

        <LayerCard title={titles.outcome}>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {displayText(
              outcome.summary || (isAgent ? 'Outcome fills when the run closes.' : '—'),
              operatorSimple,
            )}
          </Typography>
          {(outcome.sor_links || []).length > 0 && (
            <Stack spacing={0.25} sx={{ mt: 0.75 }}>
              {(outcome.sor_links || []).map((link) => (
                <Typography key={link.href || link.path || link.label} variant="caption" color="primary.main">
                  {link.label || link.path || link.href}
                </Typography>
              ))}
            </Stack>
          )}
          {!operatorSimple && outcome.canvas_id && (
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
              Canvas id: {outcome.canvas_id}
            </Typography>
          )}
        </LayerCard>
      </Stack>

      <Divider sx={{ my: 1.5 }} />
      {operatorSimple ? (
        <Typography variant="caption" color="text.disabled">
          {readOnly ? 'Read-only board.' : 'Live board.'}
        </Typography>
      ) : (
        <Typography variant="caption" color="text.disabled">
          ADR-0041 · {isAgent ? 'Agent Job Map = plan + execution + outputs' : 'Chat Job Brief = advisory only'}
          {readOnly ? ' · reopenable board' : ''}
        </Typography>
      )}
    </Box>
  );
}

function settledLabel(steps) {
  const terminal = new Set(['completed', 'failed', 'skipped', 'done', 'complete']);
  const settled = steps.filter((s) => terminal.has(s.status)).length;
  return `${settled}/${steps.length || 0} steps`;
}

OpsCanvasHost.propTypes = {
  artifact: PropTypes.object,
  readOnly: PropTypes.bool,
  flightQos: PropTypes.object,
  operatorSimple: PropTypes.bool,
};
