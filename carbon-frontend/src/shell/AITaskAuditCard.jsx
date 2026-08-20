// src/shell/AITaskAuditCard.jsx
// Sprint 23 W3-B — audit ledger for a plan run: durable steps, confirmations,
// replans, latency, tokens, provenance and actor. Read-only outcome copy
// (RULE_23 — no engine class names, no transport details); theme tokens only
// (RULE_8). Rendered after a run finishes or pauses.
import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  Divider,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import TokenOutlinedIcon from '@mui/icons-material/TokenOutlined';

import { PLAN_STATUS } from './aiTaskStatus';

// ── Small labelled value row ──────────────────────────────────────────────
function Stat({ icon, label, value }) {
  return (
    <Stack direction="row" alignItems="center" spacing={0.75}>
      {icon}
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {label}
        </Typography>
        <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
          {value}
        </Typography>
      </Box>
    </Stack>
  );
}

Stat.propTypes = {
  icon: PropTypes.node,
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};

/**
 * Audit ledger for a completed/paused plan run.
 * @param {object} props
 * @param {object} props.ledger - payload from getPlanLedger
 */
function AITaskAuditCard({ ledger }) {
  if (!ledger) return null;

  const statusMeta = PLAN_STATUS[ledger.status] || PLAN_STATUS.pending_approval;
  const usage = ledger.usage || {};
  const provenance = ledger.provenance || {};
  const steps = Array.isArray(ledger.steps) ? ledger.steps : [];
  const confirmations = Array.isArray(ledger.confirmations) ? ledger.confirmations : [];
  const actor = ledger.actor || {};

  return (
    <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ px: 1.25, py: 0.875, borderBottom: 1, borderColor: 'divider' }}>
        <HistoryOutlinedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        <Typography variant="body2" sx={{ flex: 1, fontWeight: 600, fontSize: '0.75rem' }}>
          Audit ledger
        </Typography>
        <Chip size="small" label={statusMeta.label} color={statusMeta.color} variant="outlined" sx={{ height: 18, fontSize: '0.625rem' }} />
      </Stack>

      <Stack spacing={1.25} sx={{ p: 1.25 }}>
        {/* Actor + provenance */}
        <Stack spacing={0.5}>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Requested by
          </Typography>
          <Typography variant="body2" sx={{ fontSize: '0.75rem' }}>
            {actor.display_name || actor.user_id || 'Unknown'}
          </Typography>
          <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
            {provenance.pattern && <Chip size="small" variant="outlined" label={`Pattern · ${provenance.pattern}`} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {provenance.source && <Chip size="small" variant="outlined" label={`Source · ${provenance.source}`} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {provenance.skill_name && <Chip size="small" variant="outlined" label={`Skill · ${provenance.skill_name}`} sx={{ height: 18, fontSize: '0.625rem' }} />}
            {provenance.needs_confirmation && (
              <Chip size="small" color="warning" variant="outlined" label="Requires approval" sx={{ height: 18, fontSize: '0.625rem' }} />
            )}
          </Stack>
        </Stack>

        <Divider sx={{ my: 0.25 }} />

        {/* Usage */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          <Stat icon={<ScheduleOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />} label="Latency" value={usage.total_latency_ms != null ? `${usage.total_latency_ms} ms` : '—'} />
          <Stat icon={<FactCheckOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />} label="LLM calls" value={usage.total_llm_calls ?? 0} />
          <Stat icon={<TokenOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />} label="Tokens" value={usage.total_tokens ?? 0} />
        </Box>

        <Divider sx={{ my: 0.25 }} />

        {/* Steps */}
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Steps ({steps.length})
        </Typography>
        <Stack spacing={0.5}>
          {steps.map((step) => {
            const stepMeta = PLAN_STATUS[step.status] || PLAN_STATUS.pending_approval;
            return (
              <Stack key={step.step_id} direction="row" alignItems="center" spacing={0.75} sx={{ px: 0.75, py: 0.375, borderRadius: 1, bgcolor: 'action.hover' }}>
                <CheckCircleOutlineIcon sx={{ fontSize: 14, color: step.confirmed ? 'success.main' : 'text.disabled' }} />
                <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {step.intent || `Step ${step.step_id}`}
                </Typography>
                {step.latency_ms != null && (
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
                    {step.latency_ms} ms
                  </Typography>
                )}
                {step.skipped && (
                  <Chip size="small" variant="outlined" label="Skipped" sx={{ height: 16, fontSize: '0.5625rem' }} />
                )}
                <Chip size="small" variant="outlined" label={stepMeta.label} color={stepMeta.color} sx={{ height: 16, fontSize: '0.5625rem' }} />
              </Stack>
            );
          })}
        </Stack>

        {/* Confirmations */}
        {confirmations.length > 0 && (
          <>
            <Divider sx={{ my: 0.25 }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Confirmations ({confirmations.length})
            </Typography>
            <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
              {confirmations.map((c) => (
                <Chip key={`${c.step_id}-${c.status}`} size="small" variant="outlined" label={`Step ${c.step_id} · ${c.status}`} sx={{ height: 18, fontSize: '0.625rem' }} />
              ))}
            </Stack>
          </>
        )}

        {typeof ledger.replans === 'number' && ledger.replans > 0 && (
          <Typography variant="caption" color="warning.main" sx={{ fontSize: '0.6875rem' }}>
            {ledger.replans} step{ledger.replans === 1 ? '' : 's'} required re-planning during the run.
          </Typography>
        )}

        {ledger.final_response && (
          <>
            <Divider sx={{ my: 0.25 }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Final response
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
              {ledger.final_response}
            </Typography>
          </>
        )}
      </Stack>
    </Paper>
  );
}

AITaskAuditCard.propTypes = {
  ledger: PropTypes.object,
};

export default AITaskAuditCard;
