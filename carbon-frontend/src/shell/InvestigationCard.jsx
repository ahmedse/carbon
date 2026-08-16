// src/shell/InvestigationCard.jsx
// Presentational card that renders the result of an "Investigate" run
// (conversation type `investigate`). It shows the narrative summary, the
// read-only plan steps that produced it, severity-tinted findings, and
// per-finding actions ("Chat about this", "Create rule", "Dismiss") plus a
// card-level "Re-run".
//
// The `metadata` prop mirrors the backend Phase 9-A contract:
//   {
//     type: 'investigation',
//     table_id, table_name,
//     summary: string,
//     plan_steps: [ { step, label, status: 'done' | 'llm_unavailable', detail } ],
//     findings:  [ { severity: 'high'|'medium'|'low', title, detail,
//                    recommended_action, entity_ref } ],
//     counts:    { rules_run, rules_failed, anomalies, kg_entities },
//   }

import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RefreshIcon from '@mui/icons-material/Refresh';

const SEVERITY_META = {
  high: { label: 'High', color: 'error' },
  medium: { label: 'Medium', color: 'warning' },
  low: { label: 'Low', color: 'success' },
};

const STEP_STATUS_META = {
  done: { label: 'Done', color: 'success' },
  llm_unavailable: { label: 'Synthesis unavailable', color: 'warning' },
};

export default function InvestigationCard({
  metadata,
  onRerun,
  onChatAbout,
  onCreateRule,
}) {
  const summary = metadata?.summary || '';
  const tableName = metadata?.table_name || 'table';
  const planSteps = useMemo(
    () => (Array.isArray(metadata?.plan_steps) ? metadata.plan_steps : []),
    [metadata],
  );
  const findings = useMemo(
    () => (Array.isArray(metadata?.findings) ? metadata.findings : []),
    [metadata],
  );
  const counts = metadata?.counts || {};
  const [dismissed, setDismissed] = useState(() => new Set());

  const dismissFinding = (index) => {
    setDismissed((prev) => {
      const next = new Set(prev);
      next.add(index);
      return next;
    });
  };

  return (
    <Stack spacing={1.5} sx={{ my: 1 }}>
      {/* Header */}
      <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
        <Typography variant="subtitle2" component="span">
          Investigation: {tableName}
        </Typography>
        <Chip size="small" variant="outlined" color="primary" label="Investigate" />
      </Stack>

      {/* Summary */}
      {summary && (
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
          {summary}
        </Typography>
      )}

      {/* Counts */}
      {Object.keys(counts).length > 0 && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {counts.rules_run != null && (
            <Chip size="small" label={`${counts.rules_run} rules run`} />
          )}
          {counts.rules_failed != null && (
            <Chip
              size="small"
              color={counts.rules_failed > 0 ? 'warning' : 'default'}
              label={`${counts.rules_failed} failed`}
            />
          )}
          {counts.anomalies != null && (
            <Chip size="small" label={`${counts.anomalies} anomalies`} />
          )}
          {counts.kg_entities != null && (
            <Chip size="small" label={`${counts.kg_entities} KG entities`} />
          )}
        </Stack>
      )}

      {/* Plan steps */}
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
          Plan
        </Typography>
        <Stack spacing={0.75}>
          {planSteps.map((s) => {
            const stepMeta = STEP_STATUS_META[s.status] || STEP_STATUS_META.done;
            const done = s.status !== 'llm_unavailable';
            return (
              <Stack key={s.step} direction="row" spacing={1} alignItems="flex-start">
                {done ? (
                  <CheckCircleIcon sx={{ fontSize: 16, color: 'success.main', mt: 0.25 }} />
                ) : (
                  <ErrorOutlineIcon sx={{ fontSize: 16, color: 'warning.main', mt: 0.25 }} />
                )}
                <Box sx={{ minWidth: 0 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {s.label || `Step ${s.step}`}
                    </Typography>
                    <Chip
                      size="small"
                      color={stepMeta.color}
                      label={stepMeta.label}
                      sx={{ height: 18, '& .MuiChip-label': { px: 0.75, fontSize: '0.625rem' } }}
                    />
                  </Stack>
                  {s.detail && (
                    <Typography variant="caption" color="text.secondary">
                      {s.detail}
                    </Typography>
                  )}
                </Box>
              </Stack>
            );
          })}
        </Stack>
      </Box>

      {/* Findings */}
      {findings.length > 0 && (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Findings ({findings.length})
          </Typography>
          <Stack spacing={1}>
            {findings.map((f, i) => {
              if (dismissed.has(i)) return null;
              const sev = SEVERITY_META[f.severity] || SEVERITY_META.medium;
              return (
                <Paper
                  key={i}
                  variant="outlined"
                  sx={{
                    p: 1.25,
                    borderLeft: 2,
                    borderLeftColor: `${sev.color}.main`,
                  }}
                >
                  <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {f.title || 'Finding'}
                    </Typography>
                    <Chip size="small" color={sev.color} label={sev.label} />
                  </Stack>
                  {f.detail && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      {f.detail}
                    </Typography>
                  )}
                  {f.recommended_action && (
                    <Typography variant="caption" sx={{ display: 'block', mt: 0.5, fontStyle: 'italic' }}>
                      {f.recommended_action}
                    </Typography>
                  )}
                  {f.entity_ref && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                      Entity: {f.entity_ref}
                    </Typography>
                  )}
                  <Stack direction="row" spacing={0.5} sx={{ mt: 1 }} flexWrap="wrap">
                    <Button size="small" variant="outlined" onClick={() => onChatAbout?.(f)}>
                      Chat about this
                    </Button>
                    <Button size="small" variant="outlined" color="secondary" onClick={() => onCreateRule?.(f)}>
                      Create rule
                    </Button>
                    <Button size="small" variant="text" onClick={() => dismissFinding(i)}>
                      Dismiss
                    </Button>
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        </Box>
      )}

      {/* Card-level action */}
      {onRerun && (
        <Stack direction="row" spacing={1}>
          <Button size="small" variant="outlined" startIcon={<RefreshIcon fontSize="small" />} onClick={onRerun}>
            Re-run
          </Button>
        </Stack>
      )}
    </Stack>
  );
}

InvestigationCard.propTypes = {
  metadata: PropTypes.shape({
    type: PropTypes.string,
    table_id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    table_name: PropTypes.string,
    summary: PropTypes.string,
    plan_steps: PropTypes.arrayOf(PropTypes.object),
    findings: PropTypes.arrayOf(PropTypes.object),
    counts: PropTypes.object,
  }),
  onRerun: PropTypes.func,
  onChatAbout: PropTypes.func,
  onCreateRule: PropTypes.func,
};
