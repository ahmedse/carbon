// src/shell/AIMessageBubble.jsx
import React, { Suspense, lazy, useCallback, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  Menu,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import ThumbDownAltOutlinedIcon from '@mui/icons-material/ThumbDownAltOutlined';
import ThumbUpAltOutlinedIcon from '@mui/icons-material/ThumbUpAltOutlined';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from '../utils/dateUtils';
import { formatContextLines } from '../utils/aiProvenance';
import MarkdownMessage from './MarkdownMessage';
import NLRuleTestCard from './NLRuleTestCard';
import InvestigationCard from './InvestigationCard';
import ReportDraftCard from './ReportDraftCard';

const CarbonDataGrid = lazy(() => import('../components/DataGrid/CarbonDataGrid'));

// User: flat right-aligned row, no bubble border
const USER_BUBBLE_SX = {
  alignSelf: 'flex-end',
  maxWidth: '88%',
  px: 1.25, py: 0.625,
  borderRadius: 1,
  bgcolor: 'action.hover',
};

// AI: full-width, no background, no border
const AI_BUBBLE_SX = {
  alignSelf: 'flex-start',
  width: '100%',
  px: 0, py: 0,
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
  onRetry,
  onEdit,
  onDelete,
}) {
  const [showTimestamp, setShowTimestamp] = useState(false);
  const [showActions, setShowActions] = useState(false);
  const [copied, setCopied] = useState(false);
  const [moreMenuAnchor, setMoreMenuAnchor] = useState(null);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionText, setCorrectionText] = useState('');
  const [editOpen, setEditOpen] = useState(false);
  const [editText, setEditText] = useState('');
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const handleCopyMessage = useCallback(() => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [message.content]);
  const isUser = message.role === 'user';
  const isDeleted = !!message.is_deleted;

  // Soft-deleted turns render as a dimmed placeholder — no content, no actions.
  if (isDeleted) {
    return (
      <Box sx={{ px: 1, py: 0.5, display: 'flex', alignItems: 'center', opacity: 0.6 }}>
        <Typography variant="caption" color="text.disabled" sx={{ fontStyle: 'italic' }}>
          {isUser ? 'Your message was removed.' : 'This reply was removed.'}
        </Typography>
      </Box>
    );
  }

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

  const outcomeLabel = OUTCOME_LABELS[message.outcome] || message.outcome;
  const outcomeColor =
    message.outcome === 'accepted' ? 'success' : message.outcome === 'rejected' ? 'error' : 'default';
  const showFeedback =
    !isUser && (message.outcome || onAccept || onReject || onCorrect || onPromote || onRetry || onDelete);

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
        px: 1, py: 0.25,
        position: 'relative',
      }}
      onMouseEnter={() => { setShowTimestamp(true); setShowActions(true); }}
      onMouseLeave={() => { setShowTimestamp(false); setShowActions(false); }}
    >
      {/* ⓘ provenance — floats at top-right, zero layout impact */}
      {!isUser && showProvenance && (
        <Tooltip title={<TooltipLines lines={provenanceLines} />} arrow>
          <InfoOutlinedIcon
            sx={{ position: 'absolute', top: 4, right: 2, fontSize: 11, color: 'text.disabled', cursor: 'help', opacity: 0.45, '&:hover': { opacity: 1 } }}
            aria-label="Why this answer"
          />
        </Tooltip>
      )}

      <Box sx={bubbleSx}>
        {/* status chip only on error/interrupted — inline, no row */}
        {!isUser && statusLabel && (
          <Chip size="small" color={statusColor} label={statusLabel} sx={{ height: 14, mb: 0.5, '& .MuiChip-label': { px: 0.5, fontSize: '0.6rem' } }} />
        )}

        {/* NEW: markdown for AI, pre-wrap plain text for user */}
        {isUser ? (
          editOpen ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <TextField
                size="small"
                fullWidth
                multiline
                minRows={2}
                label="Edit message"
                value={editText}
                onChange={(event) => setEditText(event.target.value)}
              />
              <Stack direction="row" spacing={0.5}>
                <Button
                  size="small"
                  variant="outlined"
                  disabled={!editText.trim()}
                  onClick={() => {
                    setEditOpen(false);
                    onEdit?.(message, editText.trim());
                  }}
                >
                  Save
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    setEditOpen(false);
                    setEditText('');
                  }}
                >
                  Cancel
                </Button>
              </Stack>
            </Box>
          ) : (
            <Typography
              variant="body2"
              sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.5 }}
            >
              {message.content}
            </Typography>
          )
        ) : (
          <MarkdownMessage content={message.content} />
        )}

        {structuredContent}

        {/* A3: outcome chip stays always-visible once set */}
        {!isUser && message.outcome && (
          <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            <Chip size="small" color={outcomeColor} label={outcomeLabel} />
            {message.correction_text && (
              <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                {message.correction_text}
              </Typography>
            )}
          </Box>
        )}

        {/* Correction form (opened from hover toolbar) */}
        {correctionOpen && (
          <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
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
          </Box>
        )}

        {/* A4: usage chip only on hover */}
        {!isUser && usageLabel && showActions && (
          <Tooltip title={<TooltipLines lines={(usageBreakdown || usageLabel).split('\n')} />} arrow>
            <Typography
              variant="caption"
              color="text.disabled"
              sx={{ display: 'block', mt: 0.5, cursor: 'help', fontSize: '0.7rem' }}
            >
              {usageLabel}
            </Typography>
          </Tooltip>
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

      {/* A3: fixed-height action row — always reserves 20px, no layout shift */}
      {!isUser && (
        <Box
          sx={{
            height: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 0.25,
            alignSelf: 'flex-start',
            opacity: (showFeedback && !correctionOpen && !message.outcome && showActions) ? 1 : 0,
            transition: 'opacity 0.12s ease',
            pointerEvents: (showFeedback && !correctionOpen && !message.outcome && showActions) ? 'auto' : 'none',
          }}
        >
          {onAccept && (
            <Tooltip title="Accept">
              <IconButton size="small" onClick={() => onAccept?.(message)} aria-label="Accept response" sx={{ p: 0.5 }}>
                <ThumbUpAltOutlinedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          )}
          {onReject && (
            <Tooltip title="Reject">
              <IconButton size="small" onClick={() => onReject?.(message)} aria-label="Reject response" sx={{ p: 0.5 }}>
                <ThumbDownAltOutlinedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title={copied ? 'Copied!' : 'Copy'}>
            <IconButton size="small" onClick={handleCopyMessage} aria-label="Copy message" sx={{ p: 0.5 }}>
              {copied ? <CheckIcon sx={{ fontSize: 14 }} /> : <ContentCopyIcon sx={{ fontSize: 14 }} />}
            </IconButton>
          </Tooltip>
          {(onCorrect || onPromote || onRetry || onDelete) && (
            <>
              <Tooltip title="More actions">
                <IconButton size="small" onClick={(e) => setMoreMenuAnchor(e.currentTarget)} aria-label="More message actions" sx={{ p: 0.5 }}>
                  <MoreVertIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
              <Menu anchorEl={moreMenuAnchor} open={Boolean(moreMenuAnchor)} onClose={() => setMoreMenuAnchor(null)}>
                {onCorrect && (
                  <MenuItem onClick={() => { setCorrectionOpen(true); setMoreMenuAnchor(null); }} sx={{ fontSize: '0.8125rem' }}>
                    Correct
                  </MenuItem>
                )}
                {onPromote && (
                  <MenuItem onClick={() => { onPromote(message); setMoreMenuAnchor(null); }} sx={{ fontSize: '0.8125rem' }}>
                    Promote
                  </MenuItem>
                )}
                {onRetry && (
                  <MenuItem onClick={() => { onRetry(message); setMoreMenuAnchor(null); }} sx={{ fontSize: '0.8125rem' }}>
                    Retry
                  </MenuItem>
                )}
                {onDelete && (
                  <MenuItem onClick={() => { setDeleteConfirmOpen(true); setMoreMenuAnchor(null); }} sx={{ fontSize: '0.8125rem' }}>
                    Delete
                  </MenuItem>
                )}
              </Menu>
            </>
          )}
        </Box>
      )}

      {/* User message actions: copy + overflow (edit/delete) */}
      {isUser && (
        <Box
          sx={{
            height: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 0.25,
            alignSelf: 'flex-end',
            opacity: showActions ? 1 : 0,
            transition: 'opacity 0.12s ease',
            pointerEvents: showActions ? 'auto' : 'none',
          }}
        >
          <Tooltip title={copied ? 'Copied!' : 'Copy'}>
            <IconButton size="small" onClick={handleCopyMessage} aria-label="Copy message" sx={{ p: 0.5 }}>
              {copied ? <CheckIcon sx={{ fontSize: 14 }} /> : <ContentCopyIcon sx={{ fontSize: 14 }} />}
            </IconButton>
          </Tooltip>
          {(onEdit || onDelete) && (
            <>
              <Tooltip title="More actions">
                <IconButton size="small" onClick={(e) => setMoreMenuAnchor(e.currentTarget)} aria-label="More message actions" sx={{ p: 0.5 }}>
                  <MoreVertIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
              <Menu anchorEl={moreMenuAnchor} open={Boolean(moreMenuAnchor)} onClose={() => setMoreMenuAnchor(null)}>
                {onEdit && (
                  <MenuItem
                    onClick={() => { setEditOpen(true); setEditText(message.content || ''); setMoreMenuAnchor(null); }}
                    sx={{ fontSize: '0.8125rem' }}
                  >
                    Edit
                  </MenuItem>
                )}
                {onDelete && (
                  <MenuItem onClick={() => { setDeleteConfirmOpen(true); setMoreMenuAnchor(null); }} sx={{ fontSize: '0.8125rem' }}>
                    Delete
                  </MenuItem>
                )}
              </Menu>
            </>
          )}
        </Box>
      )}

      {/* Delete confirmation dialog */}
      <Dialog open={deleteConfirmOpen} onClose={() => setDeleteConfirmOpen(false)}>
        <DialogTitle sx={{ fontSize: '0.9375rem' }}>Delete message?</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: '0.8125rem' }}>
            {isUser
              ? 'This removes your message and the assistant reply that follows.'
              : 'This removes this reply. The conversation will continue without it.'}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button size="small" variant="outlined" onClick={() => setDeleteConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            color="error"
            onClick={() => {
              setDeleteConfirmOpen(false);
              onDelete?.(message);
            }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {message.created_at && (
        <Typography
          variant="caption"
          color="text.disabled"
          sx={{
            alignSelf: isUser ? 'flex-end' : 'flex-start',
            fontSize: '0.68rem',
            opacity: showTimestamp ? 1 : 0,
            transition: 'opacity 0.12s ease',
            height: 16,
            lineHeight: '16px',
          }}
        >
          {formatDistanceToNow(new Date(message.created_at))}
        </Typography>
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
    is_deleted: PropTypes.bool,
    parent_id: PropTypes.string,
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
  onRetry: PropTypes.func,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
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
