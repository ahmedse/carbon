// src/shell/AIMessageBubble.jsx
import React, { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react';
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
  Divider,
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
import EditIcon from '@mui/icons-material/Edit';
import ImageOutlinedIcon from '@mui/icons-material/ImageOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import ThumbDownAltIcon from '@mui/icons-material/ThumbDownAlt';
import ThumbDownAltOutlinedIcon from '@mui/icons-material/ThumbDownAltOutlined';
import ThumbUpAltIcon from '@mui/icons-material/ThumbUpAlt';
import ThumbUpAltOutlinedIcon from '@mui/icons-material/ThumbUpAltOutlined';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from '../utils/dateUtils';
import { formatContextLines } from '../utils/aiProvenance';
import { isSafeInternalRoute } from '../utils/navigation';
import {
  cleanPlainText,
  collectMediaItems,
  copyRich,
  downloadBlob,
  downloadMediaItem,
  downloadZip,
  handleRichCopyEvent,
  slugify,
} from '../utils/exportUtils';
import { buildMessageDocx, buildMessageHtml } from '../utils/exportDocuments';
import MarkdownMessage from './MarkdownMessage';
import LongContent from './LongContent';
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

// Humanize a duration given in milliseconds: sub-second stays "950ms", seconds
// become "2.7s"/"45s", minutes "1m 12s", hours "1h 5m". Returns null for junk.
// eslint-disable-next-line react-refresh/only-export-components
export function formatDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n < 0) return null;
  if (n < 1000) return `${Math.round(n)}ms`;
  const totalSeconds = n / 1000;
  if (totalSeconds < 60) {
    return `${totalSeconds >= 10 ? Math.round(totalSeconds) : totalSeconds.toFixed(1)}s`;
  }
  const totalMinutes = Math.floor(totalSeconds / 60);
  const remSeconds = Math.round(totalSeconds % 60);
  if (totalMinutes < 60) {
    return remSeconds ? `${totalMinutes}m ${remSeconds}s` : `${totalMinutes}m`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const remMinutes = totalMinutes % 60;
  return remMinutes ? `${hours}h ${remMinutes}m` : `${hours}h`;
}

// Build a compact usage label from token_usage_json. Defensive: any missing
// field is simply omitted, so a partial usage block still renders. Latency is
// humanized (ms → s / m) so raw millisecond dumps never reach the UI.
function buildUsageLabel(usage) {
  if (!usage || typeof usage !== 'object') return null;
  const parts = [];
  if (usage.model) parts.push(String(usage.model));
  if (usage.total_tokens != null) parts.push(`${usage.total_tokens} tok`);
  if (usage.cost_usd != null) parts.push(`$${usage.cost_usd}`);
  if (usage.latency_ms != null) {
    const duration = formatDuration(usage.latency_ms);
    if (duration) parts.push(duration);
  }
  return parts.length ? parts.join(' · ') : null;
}

// Build a multi-line breakdown for the usage Tooltip.
function buildUsageBreakdown(usage) {
  if (!usage || typeof usage !== 'object') return null;
  const lines = [];
  if (usage.model) lines.push(`Model: ${usage.model}`);
  if (usage.prompt_tokens != null) lines.push(`Prompt tokens: ${usage.prompt_tokens}`);
  if (usage.completion_tokens != null) lines.push(`Completion tokens: ${usage.completion_tokens}`);
  if (usage.total_tokens != null) lines.push(`Total tokens: ${usage.total_tokens}`);
  if (usage.cost_usd != null) lines.push(`Cost: $${usage.cost_usd}`);
  if (usage.latency_ms != null) {
    const duration = formatDuration(usage.latency_ms);
    if (duration) lines.push(`Latency: ${duration}`);
  }
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
  onConfirmExecution,
  onDeclineExecution,
  onNotify,
}) {
  const [showActions, setShowActions] = useState(false);
  const [copied, setCopied] = useState(false);
  const [moreMenuAnchor, setMoreMenuAnchor] = useState(null);
  const [exportSubAnchor, setExportSubAnchor] = useState(null);
  const [mediaMenuAnchor, setMediaMenuAnchor] = useState(null);
  const [mediaItems, setMediaItems] = useState([]);
  const [hasMedia, setHasMedia] = useState(false);
  const [savingImage, setSavingImage] = useState(false);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionText, setCorrectionText] = useState('');
  const [editOpen, setEditOpen] = useState(false);
  const [editText, setEditText] = useState('');
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  // Pending-action proposal review (details + modify before confirm).
  const [detailsOpenId, setDetailsOpenId] = useState(null); // execution_id expanded
  const [editAction, setEditAction] = useState(null);       // pending action being edited
  const [editJson, setEditJson] = useState('');
  const [editJsonError, setEditJsonError] = useState('');

  const contentRef = useRef(null);
  const isUser = message.role === 'user';
  const isDeleted = !!message.is_deleted;

  // ── Rich copy / export (Phase 4C) ─────────────────────────────────────────

  /** Copy the whole message with formatting (dual-MIME: rich + plain). */
  const handleCopyWithFormatting = useCallback(async () => {
    const node = contentRef.current;
    if (node) {
      try {
        await copyRich(node, { plainText: cleanPlainText(message.content) });
      } catch {
        await navigator.clipboard.writeText(message.content);
      }
    } else {
      await navigator.clipboard.writeText(message.content);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [message.content]);

  /** Plain-text copy of the rendered message (existing behavior). */
  const handleCopyPlain = useCallback(async () => {
    const text = cleanPlainText(contentRef.current?.textContent || message.content);
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [message.content]);

  /** Copy the raw markdown source. */
  const handleCopyMarkdown = useCallback(async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [message.content]);

  /** Track whether the message renders any diagrams/figures (mutation-aware). */
  useEffect(() => {
    const node = contentRef.current;
    if (!node || isUser) return undefined;
    const update = () => setHasMedia(collectMediaItems(node).length > 0);
    update();
    const observer = new MutationObserver(update);
    observer.observe(node, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [isUser, message.content]);

  const handleOpenMediaMenu = useCallback((event) => {
    setMediaItems(collectMediaItems(contentRef.current));
    setMediaMenuAnchor(event.currentTarget);
  }, []);

  const handleSaveMedia = useCallback(
    async (item, format) => {
      setMediaMenuAnchor(null);
      setSavingImage(true);
      try {
        await downloadMediaItem(item, format);
        onNotify?.({ message: `Saved ${item.label} as ${format.toUpperCase()}`, type: 'success' });
      } catch {
        onNotify?.({ message: `Could not save ${item.label}`, type: 'error' });
      } finally {
        setSavingImage(false);
      }
    },
    [onNotify],
  );

  const handleSaveAllMedia = useCallback(async () => {
    setMediaMenuAnchor(null);
    if (mediaItems.length === 1) {
      await handleSaveMedia(mediaItems[0], 'png');
      return;
    }
    setSavingImage(true);
    try {
      await downloadZip(mediaItems, 'images.zip');
      onNotify?.({ message: `Saved ${mediaItems.length} images`, type: 'success' });
    } catch {
      onNotify?.({ message: 'Could not save images', type: 'error' });
    } finally {
      setSavingImage(false);
    }
  }, [mediaItems, handleSaveMedia, onNotify]);

  /** Native Ctrl+C on a selection inside the message → rich HTML + plain text. */
  const handleContainerCopy = useCallback((event) => {
    const handled = handleRichCopyEvent(event, { contentNode: contentRef.current });
    if (!handled) {
      event.preventDefault();
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, []);

  /** Phase 4C-B — export this message as Markdown / self-contained HTML / .docx. */
  const handleExportMessage = useCallback(
    async (format) => {
      setExportSubAnchor(null);
      setMoreMenuAnchor(null);
      const stamp = (message.created_at || new Date().toISOString()).slice(0, 10);
      const stem = `${stamp}-${message.role}-message`;
      try {
        if (format === 'markdown') {
          const blob = new Blob([message.content], { type: 'text/markdown;charset=utf-8' });
          downloadBlob(blob, `${slugify(stem)}.md`);
        } else if (format === 'html') {
          const html = await buildMessageHtml(message.content, {
            title: 'AI Message',
            meta: `${message.role} · ${message.created_at || ''}`,
          });
          downloadBlob(new Blob([html], { type: 'text/html;charset=utf-8' }), `${slugify(stem)}.html`);
        } else {
          const blob = await buildMessageDocx(message.content, {
            title: 'AI Message',
            meta: message.created_at || '',
          });
          downloadBlob(blob, `${slugify(stem)}.docx`);
        }
        onNotify?.({ message: `Exported as ${format.toUpperCase()}`, type: 'success' });
      } catch {
        onNotify?.({ message: 'Could not export message', type: 'error' });
      }
    },
    [message.content, message.created_at, message.role, onNotify],
  );

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

  // When feedback is given, the clicked thumb gets a light color: green up
  // for accepted, red down for rejected. No text, no extra row.
  const outcomeTint =
    message.outcome === 'accepted' ? 'rgba(46, 125, 50, 0.10)' : message.outcome === 'rejected' ? 'rgba(211, 47, 47, 0.10)' : undefined;
  const outcomeFg =
    message.outcome === 'accepted' ? 'success.main' : message.outcome === 'rejected' ? 'error.main' : undefined;
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
                    {canManageRules && executeMode ? (
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
                    ) : canManageRules ? (
                      <Typography variant="caption" color="text.disabled">
                        Agent mode is OFF — switch to Agent to apply these suggestions
                      </Typography>
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

  // ── AI-driven action buttons (Sprint "fly to rule detail") ────────────
  // The engine surfaces machine-readable outcomes on assistant messages:
  //   * navigate action  → a Link the user can follow to the created/found entity
  //   * pending_actions  → staged tool executions (e.g. create_dq_rule proposal)
  //                        awaiting explicit user confirmation
  // These are deterministic (never LLM prose), so a button only renders when a
  // tool actually produced it. Capability listings may carry several navigate
  // actions at once (metadata.actions); legacy messages carry a single
  // metadata.action.
  const rawActions =
    Array.isArray(metadata.actions) && metadata.actions.length > 0
      ? metadata.actions
      : metadata.action
        ? [metadata.action]
        : [];
  const navigateActions = rawActions.filter(
    (a) => a?.type === 'navigate' && isSafeInternalRoute(a.route),
  );
  const pendingActions = Array.isArray(metadata.pending_actions) ? metadata.pending_actions : [];
  const showActionRow = Boolean(
    !isUser && (navigateActions.length > 0 || pendingActions.length > 0),
  );

  // ── Pending-action proposal review ────────────────────────────────────
  // Each staged execution renders as a card: Confirm & create / Edit & confirm
  // / Decline plus an expandable "Details & JSON" section showing the proposed
  // rule definition and the exact body that will be POSTed. Editing validates
  // the JSON, then confirms the edited version in one atomic call.
  const jsonBlock = (label, value) => (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary' }}>
        {label}
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0, mt: 0.25, p: 1, borderRadius: 1,
          bgcolor: 'background.paper', border: 1, borderColor: 'divider',
          fontFamily: '"Roboto Mono", Consolas, monospace',
          fontSize: '0.7rem', lineHeight: 1.45,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          maxHeight: 220, overflow: 'auto',
        }}
      >
        {value}
      </Box>
    </Box>
  );

  const openEditAction = (pending) => {
    const body =
      pending.proposed_body && typeof pending.proposed_body === 'object'
        ? pending.proposed_body
        : {};
    setEditAction(pending);
    setEditJson(JSON.stringify(body, null, 2));
    setEditJsonError('');
  };

  const saveEditAction = () => {
    if (!editAction) return;
    let parsed;
    try {
      parsed = JSON.parse(editJson);
    } catch (err) {
      setEditJsonError(`Invalid JSON — ${err.message}`);
      return;
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      setEditJsonError('The rule body must be a JSON object.');
      return;
    }
    if (!parsed.name || !parsed.rule_type) {
      setEditJsonError('The rule body must include "name" and "rule_type".');
      return;
    }
    onConfirmExecution?.(editAction.execution_id, editAction, parsed);
    setEditAction(null);
  };

  const actionButtons = showActionRow ? (
    <Stack spacing={1} sx={{ mt: 1 }}>
      {pendingActions.map((pending) => {
        const executionId = pending.execution_id;
        if (!executionId) return null;
        const proposed = pending.proposed_rule || {};
        const proposedName = proposed.name || pending.confirmation_message || 'this proposal';
        const detailsOpen = detailsOpenId === executionId;
        const validation = pending.validation;
        const validationLabel =
          validation?.passed === true
            ? 'Preview passed'
            : validation?.passed === false
              ? 'Preview failed'
              : 'Structural validation only';
        const validationColor =
          validation?.passed === true
            ? 'success'
            : validation?.passed === false
              ? 'error'
              : 'default';
        return (
          <Paper key={executionId} variant="outlined" sx={{ p: 1.25 }}>
            <Stack spacing={1}>
              <Stack direction="row" flexWrap="wrap" gap={0.5}>
                {executeMode ? (
                  <>
                    <Button
                      size="small"
                      color="success"
                      variant="outlined"
                      disabled={!onConfirmExecution}
                      onClick={() => onConfirmExecution?.(executionId, pending)}
                      aria-label={`Confirm and create ${proposedName}`}
                    >
                      Confirm &amp; create
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<EditIcon sx={{ fontSize: 16 }} />}
                      disabled={!onConfirmExecution}
                      onClick={() => openEditAction(pending)}
                      aria-label={`Edit and confirm ${proposedName}`}
                    >
                      Edit &amp; confirm
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      variant="outlined"
                      disabled={!onDeclineExecution}
                      onClick={() => onDeclineExecution?.(executionId, pending)}
                      aria-label={`Decline ${proposedName}`}
                    >
                      Decline
                    </Button>
                  </>
                ) : (
                  <Typography variant="caption" color="text.disabled" sx={{ alignSelf: 'center' }}>
                    Agent mode is OFF — switch to Agent to confirm this action
                  </Typography>
                )}
                <Button
                  size="small"
                  variant="text"
                  onClick={() => setDetailsOpenId(detailsOpen ? null : executionId)}
                  aria-expanded={detailsOpen}
                  aria-label={`${detailsOpen ? 'Hide' : 'Show'} details for ${proposedName}`}
                >
                  {detailsOpen ? 'Hide details' : 'Details & JSON'}
                </Button>
              </Stack>

              {detailsOpen && (
                <Stack spacing={1} sx={{ pt: 0.5 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    {pending.confirmation_message || `Create DQ rule "${proposedName}"?`}
                  </Typography>
                  <Chip
                    size="small"
                    variant="outlined"
                    color={validationColor}
                    label={validationLabel}
                    sx={{ alignSelf: 'flex-start' }}
                  />
                  {validation?.passed === false && Array.isArray(validation.errors) && (
                    <Typography variant="caption" color="error">
                      {validation.errors.join(' · ')}
                    </Typography>
                  )}
                  {jsonBlock('Proposed rule (definition JSON)', JSON.stringify(proposed, null, 2))}
                  {jsonBlock(
                    'Body that will be POSTed',
                    JSON.stringify(pending.proposed_body || {}, null, 2),
                  )}
                </Stack>
              )}
            </Stack>
          </Paper>
        );
      })}
      {navigateActions.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
          {navigateActions.map((nav, idx) => (
            <Button
              key={`${nav.route}-${idx}`}
              size="small"
              variant={navigateActions.length === 1 ? 'contained' : 'outlined'}
              component={Link}
              to={nav.route}
              aria-label={nav.label || 'Open'}
            >
              {nav.label || 'Open'}
            </Button>
          ))}
        </Box>
      )}
    </Stack>
  ) : null;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        px: 1, py: 0.25,
        position: 'relative',
      }}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
      onCopy={handleContainerCopy}
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
          <LongContent content={message.content}>
            <Box ref={contentRef} data-testid="message-content">
              <MarkdownMessage content={message.content} />
            </Box>
          </LongContent>
        )}

        {structuredContent}

        {actionButtons}

        {/* Correction note stays inline if the user submitted a correction. */}
        {!isUser && message.outcome && message.correction_text && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, fontStyle: 'italic', display: 'block' }}>
            {message.correction_text}
          </Typography>
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

        {/* Usage + time-ago metadata now live on the hover action row below. */}

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

      {/* A3: fixed-height action row — always reserves 20px, no layout shift.
          Usage + time-ago meta share this line (right-aligned) so latency and
          timestamps read inline with the feedback actions. */}
      {!isUser && (
        <Box
          data-testid="message-actions-row"
          sx={{
            height: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 0.25,
            width: '100%',
            minWidth: 0,
            alignSelf: 'flex-start',
            opacity: (showFeedback && !correctionOpen && showActions) ? 1 : 0,
            transition: 'opacity 0.12s ease',
            pointerEvents: (showFeedback && !correctionOpen && showActions) ? 'auto' : 'none',
          }}
        >
          {/* Feedback just colors the thumb the user clicked (green up / red
              down) — all other tools stay exactly as they were. */}
          {onAccept && (
            <Tooltip title={message.outcome === 'accepted' ? 'Accepted' : 'Accept'}>
              <IconButton
                size="small"
                onClick={() => onAccept?.(message)}
                aria-label="Accept response"
                data-testid={message.outcome === 'accepted' ? 'message-outcome-accepted' : 'accept-response'}
                sx={{
                  p: 0.5,
                  ...(message.outcome === 'accepted'
                    ? {
                        bgcolor: outcomeTint,
                        color: outcomeFg,
                        '&:hover': { bgcolor: outcomeTint, color: outcomeFg },
                      }
                    : {}),
                }}
              >
                {message.outcome === 'accepted' ? (
                  <ThumbUpAltIcon sx={{ fontSize: 14 }} />
                ) : (
                  <ThumbUpAltOutlinedIcon sx={{ fontSize: 14 }} />
                )}
              </IconButton>
            </Tooltip>
          )}
          {onReject && (
            <Tooltip title={message.outcome === 'rejected' ? 'Rejected' : 'Reject'}>
              <IconButton
                size="small"
                onClick={() => onReject?.(message)}
                aria-label="Reject response"
                data-testid={message.outcome === 'rejected' ? 'message-outcome-rejected' : 'reject-response'}
                sx={{
                  p: 0.5,
                  ...(message.outcome === 'rejected'
                    ? {
                        bgcolor: outcomeTint,
                        color: outcomeFg,
                        '&:hover': { bgcolor: outcomeTint, color: outcomeFg },
                      }
                    : {}),
                }}
              >
                {message.outcome === 'rejected' ? (
                  <ThumbDownAltIcon sx={{ fontSize: 14 }} />
                ) : (
                  <ThumbDownAltOutlinedIcon sx={{ fontSize: 14 }} />
                )}
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title={copied ? 'Copied with formatting' : 'Copy with formatting'}>
            <IconButton size="small" onClick={handleCopyWithFormatting} aria-label="Copy message" sx={{ p: 0.5 }}>
              {copied ? <CheckIcon sx={{ fontSize: 14 }} /> : <ContentCopyIcon sx={{ fontSize: 14 }} />}
            </IconButton>
          </Tooltip>
          {hasMedia && (
            <>
              <Tooltip title="Save images">
                <IconButton size="small" onClick={handleOpenMediaMenu} aria-label="Save images" disabled={savingImage} sx={{ p: 0.5 }}>
                  <ImageOutlinedIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
              <Menu anchorEl={mediaMenuAnchor} open={Boolean(mediaMenuAnchor)} onClose={() => setMediaMenuAnchor(null)}>
                {mediaItems.map((item, idx) => (
                  <React.Fragment key={`${item.nameBase}-${idx}`}>
                    <MenuItem onClick={() => handleSaveMedia(item, 'png')} disabled={savingImage} sx={{ fontSize: '0.8125rem' }}>
                      {item.label} — PNG
                    </MenuItem>
                    {item.svg && (
                      <MenuItem onClick={() => handleSaveMedia(item, 'svg')} disabled={savingImage} sx={{ fontSize: '0.8125rem' }}>
                        {item.label} — SVG
                      </MenuItem>
                    )}
                  </React.Fragment>
                ))}
                {mediaItems.length > 1 && (
                  <MenuItem onClick={handleSaveAllMedia} disabled={savingImage} sx={{ fontSize: '0.8125rem' }}>
                    Save all ({mediaItems.length})
                  </MenuItem>
                )}
              </Menu>
            </>
          )}
          {(onCorrect || onPromote || onRetry || onDelete) && (
            <>
              <Tooltip title="More actions">
                <IconButton size="small" onClick={(e) => setMoreMenuAnchor(e.currentTarget)} aria-label="More message actions" sx={{ p: 0.5 }}>
                  <MoreVertIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
              <Menu anchorEl={moreMenuAnchor} open={Boolean(moreMenuAnchor)} onClose={() => setMoreMenuAnchor(null)}>
                <MenuItem onClick={() => { handleCopyPlain(); setMoreMenuAnchor(null); }} sx={{ fontSize: '0.8125rem' }}>
                  Copy plain text
                </MenuItem>
                <MenuItem onClick={() => { handleCopyMarkdown(); setMoreMenuAnchor(null); }} sx={{ fontSize: '0.8125rem' }}>
                  Copy markdown
                </MenuItem>
                <MenuItem
                  onClick={(e) => setExportSubAnchor(e.currentTarget)}
                  sx={{ fontSize: '0.8125rem' }}
                >
                  Export message
                </MenuItem>
                <Menu
                  anchorEl={exportSubAnchor}
                  open={Boolean(exportSubAnchor)}
                  onClose={() => setExportSubAnchor(null)}
                  anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                >
                  <MenuItem onClick={() => handleExportMessage('markdown')} sx={{ fontSize: '0.8125rem' }}>
                    Markdown (.md)
                  </MenuItem>
                  <MenuItem onClick={() => handleExportMessage('html')} sx={{ fontSize: '0.8125rem' }}>
                    HTML (.html)
                  </MenuItem>
                  <MenuItem onClick={() => handleExportMessage('docx')} sx={{ fontSize: '0.8125rem' }}>
                    Word (.docx)
                  </MenuItem>
                </Menu>
                <Divider sx={{ my: 0.5 }} />
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
          {/* Usage + time-ago, right-aligned on the same hover line */}
          <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0, pl: 1 }}>
            {usageLabel && (
              <Tooltip title={<TooltipLines lines={(usageBreakdown || usageLabel).split('\n')} />} arrow>
                <Typography
                  variant="caption"
                  color="text.disabled"
                  noWrap
                  sx={{ fontSize: '0.68rem', cursor: 'help', maxWidth: 240 }}
                >
                  {usageLabel}
                </Typography>
              </Tooltip>
            )}
            {message.created_at && (
              <Typography variant="caption" color="text.disabled" noWrap sx={{ fontSize: '0.68rem' }}>
                {formatDistanceToNow(new Date(message.created_at))}
              </Typography>
            )}
          </Box>
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
            <IconButton size="small" onClick={handleCopyPlain} aria-label="Copy message" sx={{ p: 0.5 }}>
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
          {/* Time-ago on the same hover line */}
          {message.created_at && (
            <Typography variant="caption" color="text.disabled" noWrap sx={{ fontSize: '0.68rem', ml: 0.75 }}>
              {formatDistanceToNow(new Date(message.created_at))}
            </Typography>
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

      {/* Edit & confirm dialog — modify the staged rule body before creating.
          Save validates the JSON, then confirms the edited version atomically. */}
      <Dialog
        open={Boolean(editAction)}
        onClose={() => setEditAction(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ fontSize: '0.9375rem' }}>
          Edit proposed rule{editAction?.proposed_rule?.name ? ` — ${editAction.proposed_rule.name}` : ''}
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: '0.8125rem', mb: 1.25 }}>
            Edit the JSON body that will be sent to create the rule, then confirm.
            Nothing is created until you save — you can also cancel or decline.
          </DialogContentText>
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={12}
            maxRows={26}
            value={editJson}
            onChange={(event) => {
              setEditJson(event.target.value);
              if (editJsonError) setEditJsonError('');
            }}
            error={Boolean(editJsonError)}
            helperText={editJsonError || 'Must be a JSON object with "name" and "rule_type".'}
            slotProps={{
              input: {
                sx: {
                  fontFamily: '"Roboto Mono", Consolas, monospace',
                  fontSize: '0.78rem',
                },
              },
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            size="small"
            variant="outlined"
            onClick={() => openEditAction(editAction)}
            disabled={!editAction}
          >
            Reset
          </Button>
          <Button size="small" variant="outlined" onClick={() => setEditAction(null)}>
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            color="success"
            disabled={!editAction}
            onClick={saveEditAction}
          >
            Save &amp; confirm
          </Button>
        </DialogActions>
      </Dialog>

      {/* Timestamp moved onto the hover action rows above (shared line). */}
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
  onConfirmExecution: PropTypes.func,
  onDeclineExecution: PropTypes.func,
  onNotify: PropTypes.func,
};

export default AIMessageBubble;
