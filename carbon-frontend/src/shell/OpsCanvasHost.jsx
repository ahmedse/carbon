/** Ops Canvas Job Map host — ADR-0041 closed typed board (no free HTML). */
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
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
import MapOutlinedIcon from '@mui/icons-material/MapOutlined';

const LAYER_ORDER = [
  ['intent', 'Intent'],
  ['job_map', 'Job map'],
  ['live_run', 'Live run'],
  ['evidence', 'Evidence'],
  ['outcome', 'Outcome'],
];

function LayerCard({ title, children, muted }) {
  return (
    <Box
      sx={{
        border: 1,
        borderColor: 'divider',
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
          color: 'text.secondary',
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
};

/**
 * @param {object} props
 * @param {object} props.artifact — serialized AIArtifact (job_map)
 * @param {boolean} [props.readOnly]
 * @param {object} [props.flightQos] — optional FlightDirector overlay
 */
export default function OpsCanvasHost({ artifact, readOnly = true, flightQos = null }) {
  const payload = useMemo(() => {
    const raw = artifact?.content_json;
    if (!raw || typeof raw !== 'object') return null;
    if (raw.kind && raw.kind !== 'job_map') return null;
    return raw;
  }, [artifact]);

  const layers = payload?.layers || {};
  const mode = payload?.mode || 'chat';
  const related = payload?.related_object;

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
  const showLive = mode === 'agent' || progress > 0 || qos;

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }} data-testid="ops-canvas-host">
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
        <MapOutlinedIcon sx={{ fontSize: 18, color: 'primary.main' }} />
        <Typography variant="subtitle2" fontWeight={700} sx={{ flex: 1 }}>
          {artifact?.title || payload.title || 'Job Map'}
        </Typography>
        <Chip
          size="small"
          label={mode === 'agent' ? 'Agent' : 'Chat brief'}
          color={mode === 'agent' ? 'warning' : 'info'}
          variant="outlined"
        />
        {readOnly && (
          <Chip size="small" label="Read-only" variant="outlined" />
        )}
      </Stack>

      {related?.type && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          Attached: {related.type}
          {related.id ? ` #${related.id}` : ''}
          {related.label ? ` — ${related.label}` : ''}
        </Typography>
      )}

      <Stack spacing={1.25}>
        <LayerCard title="Intent">
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {intent.ask || '—'}
          </Typography>
          {intent.success_criteria ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              Success: {intent.success_criteria}
            </Typography>
          ) : null}
          <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
            Contract: {intent.contract || (mode === 'chat' ? 'advisory' : 'agent')}
          </Typography>
        </LayerCard>

        <LayerCard title="Job map">
          {(job.steps || []).length === 0 ? (
            <Typography variant="caption" color="text.secondary">No steps yet.</Typography>
          ) : (
            <Stack spacing={0.5}>
              {(job.steps || []).map((s) => (
                <Stack key={s.id || s.title} direction="row" spacing={1} alignItems="center">
                  <Chip size="small" label={s.status || 'pending'} sx={{ minWidth: 72 }} />
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {s.title}
                  </Typography>
                  {s.tool ? (
                    <Typography variant="caption" color="text.disabled">{s.tool}</Typography>
                  ) : null}
                </Stack>
              ))}
            </Stack>
          )}
          {(job.tools || []).length > 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Tools: {(job.tools || []).join(', ')}
            </Typography>
          )}
          {(job.capabilities || []).length > 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              CBAC: {(job.capabilities || []).join(', ')}
            </Typography>
          )}
        </LayerCard>

        {showLive && (
          <LayerCard title="Live run" muted={mode === 'chat'}>
            <Stack spacing={0.75}>
              <Typography variant="caption" color="text.secondary">
                Status: {live.status || 'idle'}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.max(0, Math.min(100, progress))}
                sx={{ height: 6, borderRadius: 1 }}
              />
              {qos && typeof qos === 'object' && (
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
              )}
              {(live.blockers || []).length > 0 && (
                <Typography variant="caption" color="warning.main">
                  Blockers: {(live.blockers || []).join('; ')}
                </Typography>
              )}
              {live.pending_consent && (
                <Typography variant="caption" color="warning.main">
                  Consent pending: {String(live.pending_consent)}
                </Typography>
              )}
            </Stack>
          </LayerCard>
        )}

        <LayerCard title="Evidence">
          {evidence.headline ? (
            <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
              {evidence.headline}
            </Typography>
          ) : null}
          {evidence.prose ? (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1, whiteSpace: 'pre-wrap' }}>
              {String(evidence.prose).slice(0, 800)}
            </Typography>
          ) : null}
          {(evidence.tables || []).slice(0, 2).map((tbl, idx) => (
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
                  {(tbl.rows || []).slice(0, 5).map((row, ri) => (
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
              Caveats: {(evidence.caveats || []).map((c) => (typeof c === 'string' ? c : c.text || '')).join('; ')}
            </Typography>
          )}
          {(evidence.sources || []).length > 0 && (
            <Typography variant="caption" color="text.disabled" display="block" sx={{ mt: 0.5 }}>
              Sources: {(evidence.sources || []).length}
            </Typography>
          )}
          {!evidence.headline && !(evidence.tables || []).length && (
            <Typography variant="caption" color="text.secondary">No evidence yet.</Typography>
          )}
        </LayerCard>

        <LayerCard title="Outcome">
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {outcome.summary || '—'}
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
          {outcome.canvas_id && (
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 0.5 }}>
              Canvas id: {outcome.canvas_id}
            </Typography>
          )}
        </LayerCard>
      </Stack>

      <Divider sx={{ my: 1.5 }} />
      <Typography variant="caption" color="text.disabled">
        ADR-0041 Ops Canvas · layers {LAYER_ORDER.map(([, l]) => l).join(' · ')}
      </Typography>
    </Box>
  );
}

OpsCanvasHost.propTypes = {
  artifact: PropTypes.object,
  readOnly: PropTypes.bool,
  flightQos: PropTypes.object,
};
