// src/shell/AIMessageBubble.jsx
import React, { Suspense, lazy, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, Paper, Stack, TextField, Tooltip, Typography } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from '../utils/dateUtils';
import { formatContextLines } from '../utils/aiProvenance';
import NLRuleTestCard from './NLRuleTestCard';
import InvestigationCard from './InvestigationCard';
import ReportDraftCard from './ReportDraftCard';

const CarbonDataGrid = lazy(() => import('../components/DataGrid/CarbonDataGrid'));

const USER_BUBBLE_SX = {
  alignSelf: 'flex-end',
  maxWidth: '85%',
  py: 1,
  px: 1.5,
  borderRadius: 2,
  borderBottomRightRadius: 1,
  bgcolor: 'action.selected',
  border: 1,
  borderColor: 'primary.main',
};

const AI_BUBBLE_SX = {
  alignSelf: 'flex-start',
  maxWidth: '85%',
  py: 1,
  px: 1.5,
  borderRadius: 2,
  borderBottomLeftRadius: 1,
  bgcolor: 'background.paper',
  border: 1,
  borderColor: 'divider',
};

const META_SX = {
  display: 'flex',
  alignItems: 'center',
  gap: 0.5,
  mb: 0.5,
  opacity: 0.7,
};

const OUTCOME_LABELS = {
  accepted: 'Accepted',
  rejected: 'Rejected',
  corrected: 'Corrected',
  ignored: 'Ignored',
};

function normalizeMetadata(message) {
  return message.metadata || message.metadata_json || {};
}

function toGridRows(rows) {
  return (rows || []).map((r, idx) => ({ id: r.id ?? idx, ...r }));
}

function toGridColumns(rows, metadataColumns) {
  if (Array.isArray(metadataColumns) && metadataColumns.length > 0) {
    return metadataColumns.map((col) => {
      const field = typeof col === 'string' ? col : col.field;
      const headerName = typeof col === 'string' ? col : (col.headerName || col.field);
      return {
        field,
        headerName,
        flex: 1,
        minWidth: 120,
      };
    });
  }
  const sample = rows?.[0] || {};
  return Object.keys(sample).map((k) => ({
    field: k,
    headerName: k,
    flex: 1,
    minWidth: 120,
  }));
}

function confidenceLabel(confidence) {
  if (confidence == null) return null;
  const pct = confidence > 1 ? confidence : Math.round(confidence * 100);
  return `${pct}%`;
}

// Build a compact usage chip label from token_usage_json. Defensive: any
// missing field is simply omitted, so a partial usage block still renders.
function buildUsageLabel(usage) {
  if (!usage || typeof usage !== 'object') return null;
  const parts = [];
  if (usage.model) parts.push(String(usage.model));
  if (usage.total_tokens != null) parts.push(`${usage.total_tokens} tok`);
  if (usage.cost_usd != null) parts.push(`$${usage.cost_usd}`);
  if (usage.latency_ms != null) parts.push(`${usage.latency_ms}ms`);
  return parts.length ? parts.join(' · ') : null;
}

// Build a multi-line breakdown for the usage chip Tooltip.
function buildUsageBreakdown(usage) {
  if (!usage || typeof usage !== 'object') return null;
  const lines = [];
  if (usage.model) lines.push(`Model: ${usage.model}`);
  if (usage.prompt_tokens != null) lines.push(`Prompt tokens: ${usage.prompt_tokens}`);
  if (usage.completion_tokens != null) lines.push(`Completion tokens: ${usage.completion_tokens}`);
  if (usage.total_tokens != null) lines.push(`Total tokens: ${usage.total_tokens}`);
  if (usage.cost_usd != null) lines.push(`Cost: $${usage.cost_usd}`);
  if (usage.latency_ms != null) lines.push(`Latency: ${usage.latency_ms}ms`);
  return lines.length ? lines.join('\n') : null;
}

// Count org units from a frozen Scope (scope_json). ["*"] means all access.
function orgUnitCount(scopeJson) {
  const ids = scopeJson?.org_unit_ids;
  if (!Array.isArray(ids)) return null;
  if (ids.length === 1 && ids[0] === '*') return 'All';
  return ids.length;
}

// Render a stacked, multi-line Tooltip title.
function TooltipLines({ lines }) {
  if (!Array.isArray(lines) || lines.length === 0) return null;
  return (
    <Box component="span" sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
      {lines.map((line) => (
        <Typography key={line} component="span" variant="caption" sx={{ display: 'block' }}>
          {line}
        </Typography>
      ))}
    </Box>
  );
}

function AIMessageBubble({
  message,
  onAcceptSuggestion,
  onRejectSuggestion,
  canManageRules = true,
  onAccept,
  onReject,
  onCorrect,
  onFollowUp,
  onPromote,
  conversationType,
  appIdentifier,
  scopeJson,
  executeMode = false,
  onTestLive,
  onSave,
  onRerun,
  onChatAbout,
  onCreateRule,
  onSaveReportArtifact,
  onExportReport,
  onRedraftReport,
}) {
  const [showTimestamp, setShowTimestamp] = useState(false);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionText, setCorrectionText] = useState('');
  const isUser = message.role === 'user';
  const metadata = normalizeMetadata(message);
  const followUps = metadata.follow_up_questions || [];
  const usageLabel = buildUsageLabel(message.token_usage_json);
  const usageBreakdown = buildUsageBreakdown(message.token_usage_json);
  const statusLabel = message.status === 'stopped' ? 'Interrupted' : message.status === 'failed' ? 'Error' : null;
  const statusColor = message.status === 'stopped' ? 'warning' : 'error';

  // "Why this answer" provenance: prefer the backend's top-level serialized
  // ``message.provenance`` (built by ``_build_message_provenance``), falling
  // back to a provenance block embedded in ``metadata_json``, then to scope/type
  // info from conversation props.
  const provenancePayload = message.provenance || metadata?.provenance;
  const provenanceLines = [];
  if (provenancePayload && typeof provenancePayload === 'object') {
    if (provenancePayload.model) provenanceLines.push(`Model: ${provenancePayload.model}`);
    if (conversationType) provenanceLines.push(`Type: ${conversationType}`);
    if (provenancePayload.engine_turn_id) provenanceLines.push(`Turn: ${provenancePayload.engine_turn_id}`);
    if (appIdentifier || provenancePayload.app_identifier)
      provenanceLines.push(`App: ${appIdentifier || provenancePayload.app_identifier}`);
    const guardResults = provenancePayload.guard_results;
    if (guardResults && typeof guardResults === 'object') {
      const guards = Object.entries(guardResults)
        .map(([g, ok]) => `${g}: ${ok ? '✓' : '✗'}`)
        .join(' · ');
      if (guards) provenanceLines.push(`Guards: ${guards}`);
    }
    provenanceLines.push(...formatContextLines(provenancePayload.context_snapshot));
    const scopeSnap = provenancePayload.scope_snapshot || scopeJson;
    const units = orgUnitCount(scopeSnap);
    if (units !== null) provenanceLines.push(`Org units: ${units}`);
  } else {
    // Fallback: build from conversation props.
    if (conversationType) provenanceLines.push(`Type: ${conversationType}`);
    if (appIdentifier) provenanceLines.push(`App: ${appIdentifier}`);
    const scopeUnits = orgUnitCount(scopeJson);
    if (scopeUnits !== null) provenanceLines.push(`Org units: ${scopeUnits}`);
  }
  if (!provenanceLines.length) provenanceLines.push('Structured AI response');
  const hasStructured = !!metadata?.type;
  const hasScope = !!conversationType || !!appIdentifier || scopeJson?.org_unit_ids != null;
  const showProvenance = !isUser && (hasStructured || hasScope);

  const bubbleSx = isUser ? USER_BUBBLE_SX : AI_BUBBLE_SX;
  const Icon = isUser ? PersonIcon : SmartToyIcon;

  const outcomeLabel = OUTCOME_LABELS[message.outcome] || message.outcome;
  const outcomeColor =
    message.outcome === 'accepted' ? 'success' : message.outcome === 'rejected' ? 'error' : 'default';
  const showFeedback = !isUser && (message.outcome || onAccept || onReject || onCorrect || onPromote);

  const renderStructuredContent = () => {
    if (isUser || !metadata?.type) return null;

    if (metadata.type === 'dq_suggestions') {
      const suggestions = metadata.suggestions || metadata.items || [];
      return (
        <Box sx={{ mt: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            AI suggests {suggestions.length} DQ rule{suggestions.length === 1 ? '' : 's'}:
          </Typography>
          <Stack spacing={1}>
            {suggestions.map((s, i) => (
              <Paper key={s.id || s.suggestion_id || i} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" justifyContent="space-between" spacing={1}>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {s.definition?.name || s.name || `Suggestion ${i + 1}`}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {s.rationale || s.explanation || 'AI-generated suggestion'}
                    </Typography>
                    {confidenceLabel(s.confidence) && (
                      <Box sx={{ mt: 0.75 }}>
                        <Chip size="small" variant="outlined" label={confidenceLabel(s.confidence)} />
                      </Box>
                    )}
                  </Box>
                  <Stack direction="row" spacing={0.5}>
                    {canManageRules ? (
                      <>
                        {onTestLive && (
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => onTestLive?.(s)}
                          >
                            Test live
                          </Button>
                        )}
                        <Button
                          size="small"
                          color="success"
                          variant="outlined"
                          onClick={() => onAcceptSuggestion?.(s)}
                        >
                          Accept
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          variant="outlined"
                          onClick={() => onRejectSuggestion?.(s)}
                        >
                          Reject
                        </Button>
                      </>
                    ) : (
                      <Typography variant="caption" color="text.disabled">
                        Requires DQ manage permission
                      </Typography>
                    )}
                  </Stack>
                </Stack>
              </Paper>
            ))}
          </Stack>
        </Box>
      );
    }

    if (metadata.type === 'nl_query_result') {
      const rows = metadata.rows || metadata.result_rows || [];
      const columns = toGridColumns(rows, metadata.columns);
      return (
        <Box sx={{ mt: 1 }}>
          {metadata.sql && (
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'monospace',
                bgcolor: 'action.hover',
                p: 1,
                borderRadius: 1,
                display: 'block',
                mb: 1,
                whiteSpace: 'pre-wrap',
              }}
            >
              {metadata.sql}
            </Typography>
          )}
          <Box sx={{ height: 220 }}>
            <Suspense
              fallback={(
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <Typography variant="caption" color="text.secondary">
                    Loading results…
                  </Typography>
                </Box>
              )}
            >
              <CarbonDataGrid
                rows={toGridRows(rows)}
                columns={columns}
                density="compact"
                hideFooter={rows.length <= 25}
                getRowId={(row) => row.id}
                emptyMessage="No rows returned"
              />
            </Suspense>
          </Box>
          <Typography variant="caption" color="text.secondary">
            {metadata.row_count ?? rows.length} rows
          </Typography>
        </Box>
      );
    }

    if (metadata.type === 'nl_rule_test') {
      return (
        <Box sx={{ mt: 1 }}>
          <NLRuleTestCard
            metadata={metadata}
            executeMode={executeMode}
            onSave={onSave}
          />
        </Box>
      );
    }

    if (metadata.type === 'investigation') {
      return (
        <Box sx={{ mt: 1 }}>
          <InvestigationCard
            metadata={metadata}
            onRerun={onRerun}
            onChatAbout={onChatAbout}
            onCreateRule={onCreateRule}
          />
        </Box>
      );
    }

    if (metadata.type === 'report') {
      return (
        <Box sx={{ mt: 1 }}>
          <ReportDraftCard
            metadata={metadata}
            onSaveArtifact={onSaveReportArtifact}
            onExport={onExportReport}
            onRedraft={onRedraftReport}
          />
        </Box>
      );
    }

    if (metadata.type === 'anomalies') {
      const anomalies = metadata.anomalies || [];
      return (
        <Box sx={{ mt: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Anomalies detected:
          </Typography>
          <Stack spacing={1}>
            {anomalies.map((a, i) => {
              const severity = a.severity === 'error' ? 'error' : 'warning';
              const detailsPath = a.rule_id ? `/dq/rules/${a.rule_id}/results` : '/dq';
              return (
                <Paper
                  key={a.id || i}
                  variant="outlined"
                  sx={{
                    p: 1.5,
                    borderLeft: 2,
                    borderLeftColor: severity === 'error' ? 'error.main' : 'warning.main',
                  }}
                >
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {a.metric || a.name || 'Anomaly'}
                    </Typography>
                    <Chip
                      size="small"
                      color={severity}
                      label={a.z_score != null ? `z=${Number(a.z_score).toFixed(1)}` : severity}
                    />
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    {a.explanation || 'Unexpected distribution or trend detected.'}
                  </Typography>
                  <Button
                    size="small"
                    variant="outlined"
                    component={Link}
                    to={detailsPath}
                    sx={{ mt: 1 }}
                  >
                    View details
                  </Button>
                </Paper>
              );
            })}
          </Stack>
        </Box>
      );
    }

    return null;
  };

  const structuredContent = renderStructuredContent();

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        px: 1.5,
        py: 0.5,
      }}
      onMouseEnter={() => setShowTimestamp(true)}
      onMouseLeave={() => setShowTimestamp(false)}
    >
      <Box sx={bubbleSx}>
        <Box sx={META_SX}>
          <Icon sx={{ fontSize: 13 }} />
          <Typography variant="caption" fontWeight={600}>
            {isUser ? 'You' : 'AI'}
          </Typography>
          {statusLabel && (
            <Chip size="small" color={statusColor} label={statusLabel} sx={{ height: 16, '& .MuiChip-label': { px: 0.5, fontSize: '0.625rem' } }} />
          )}
          {showProvenance && (
            <Tooltip title={<TooltipLines lines={provenanceLines} />} arrow>
              <InfoOutlinedIcon
                sx={{ fontSize: 13, color: 'text.secondary', cursor: 'help' }}
                aria-label="Why this answer"
              />
            </Tooltip>
          )}
        </Box>

        <Typography
          variant="body2"
          sx={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            lineHeight: 1.5,
          }}
        >
          {message.content}
        </Typography>

        {structuredContent}

        {showFeedback && (
          <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
            {message.outcome ? (
              <>
                <Chip size="small" color={outcomeColor} label={outcomeLabel} />
                {message.correction_text ? (
                  <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                    {message.correction_text}
                  </Typography>
                ) : null}
              </>
            ) : correctionOpen ? (
              <>
                <TextField
                  size="small"
                  fullWidth
                  multiline
                  minRows={2}
                  label="Correction"
                  value={correctionText}
                  onChange={(event) => setCorrectionText(event.target.value)}
                  placeholder="Describe what the answer should have said…"
                />
                <Stack direction="row" spacing={0.5}>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={!correctionText.trim()}
                    onClick={() => onCorrect?.(message, correctionText.trim())}
                  >
                    Save
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => {
                      setCorrectionOpen(false);
                      setCorrectionText('');
                    }}
                  >
                    Cancel
                  </Button>
                </Stack>
              </>
            ) : (
              <Stack direction="row" spacing={0.5} flexWrap="wrap">
                <Button
                  size="small"
                  variant="outlined"
                  color="success"
                  onClick={() => onAccept?.(message)}
                >
                  Accept
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  color="error"
                  onClick={() => onReject?.(message)}
                >
                  Reject
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => setCorrectionOpen(true)}
                >
                  Correct
                </Button>
                {onPromote && (
                  <Button
                    size="small"
                    variant="outlined"
                    color="secondary"
                    onClick={() => onPromote(message)}
                  >
                    Promote
                  </Button>
                )}
              </Stack>
            )}
          </Box>
        )}

        {usageLabel && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
            <Tooltip
              title={<TooltipLines lines={(usageBreakdown || usageLabel).split('\n')} />}
              arrow
            >
              <Chip
                size="small"
                variant="outlined"
                label={usageLabel}
                sx={{ color: 'text.secondary' }}
              />
            </Tooltip>
          </Box>
        )}

        {followUps.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
            {followUps.map((q, i) => (
              <Chip
                key={i}
                label={q}
                size="small"
                variant="outlined"
                color="primary"
                clickable
                onClick={() => onFollowUp?.(q)}
              />
            ))}
          </Box>
        )}
      </Box>

      {showTimestamp && message.created_at && (
        <Tooltip title={new Date(message.created_at).toLocaleString()}>
          <Typography
            variant="caption"
            color="text.disabled"
            sx={{
              alignSelf: isUser ? 'flex-end' : 'flex-start',
              mt: 0.25,
              mx: 0.5,
            }}
          >
            {formatDistanceToNow(new Date(message.created_at))}
          </Typography>
        </Tooltip>
      )}
    </Box>
  );
}

AIMessageBubble.propTypes = {
  message: PropTypes.shape({
    role: PropTypes.string.isRequired,
    content: PropTypes.string.isRequired,
    created_at: PropTypes.string,
    metadata: PropTypes.object,
    metadata_json: PropTypes.object,
    token_usage_json: PropTypes.object,
    status: PropTypes.string,
    outcome: PropTypes.string,
    correction_text: PropTypes.string,
  }).isRequired,
  onAcceptSuggestion: PropTypes.func,
  onRejectSuggestion: PropTypes.func,
  canManageRules: PropTypes.bool,
  onAccept: PropTypes.func,
  onSaveReportArtifact: PropTypes.func,
  onExportReport: PropTypes.func,
  onRedraftReport: PropTypes.func,
  onReject: PropTypes.func,
  onCorrect: PropTypes.func,
  onFollowUp: PropTypes.func,
  onPromote: PropTypes.func,
  conversationType: PropTypes.string,
  appIdentifier: PropTypes.string,
  scopeJson: PropTypes.object,
  executeMode: PropTypes.bool,
  onTestLive: PropTypes.func,
  onSave: PropTypes.func,
  onRerun: PropTypes.func,
  onChatAbout: PropTypes.func,
  onCreateRule: PropTypes.func,
};

export default AIMessageBubble;
