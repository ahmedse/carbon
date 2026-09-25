// src/shell/AIMessageBubble.jsx
import React, { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  Menu,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DownloadIcon from '@mui/icons-material/Download';
import EditIcon from '@mui/icons-material/Edit';
import ImageOutlinedIcon from '@mui/icons-material/ImageOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import ThumbDownAltIcon from '@mui/icons-material/ThumbDownAlt';
import ThumbDownAltOutlinedIcon from '@mui/icons-material/ThumbDownAltOutlined';
import ThumbUpAltIcon from '@mui/icons-material/ThumbUpAlt';
import ThumbUpAltOutlinedIcon from '@mui/icons-material/ThumbUpAltOutlined';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from '../utils/dateUtils';
import { formatContextLines, normalizeProvenanceSources } from '../utils/aiProvenance';
import { isSafeInternalRoute } from '../utils/navigation';
import {
  presentConsentExpandLabel,
  presentTechnicalDetailsLabel,
} from './presentationPlane';
import { resolveBackendUrl } from '../config';
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
import { KeyValueOutput } from '../components/ai/StepOutputRenderer';
import MarkdownMessage from './MarkdownMessage';
import EnvelopeMessage from './EnvelopeMessage';
import LongContent from './LongContent';
import { splitAnswerAppendix } from './splitAnswerAppendix';
import NLRuleTestCard from './NLRuleTestCard';
import InvestigationCard from './InvestigationCard';
import ReportDraftCard from './ReportDraftCard';
import ConfidenceIndicator from './ConfidenceIndicator';
import AIGeneratedBadge from './AIGeneratedBadge';
import ReasoningTrace from './ReasoningTrace';
import PlanningHeader from './PlanningHeader';
import PlanProposalForm from './PlanProposalForm';
import { useAuth } from '../auth/AuthContext';
import { commitPlanProposal } from '../api/aiWorkspace';
import SuggestionDiff from './SuggestionDiff';

const CarbonDataGrid = lazy(() => import('../components/DataGrid/CarbonDataGrid'));

// User: compact right-aligned row — keep a soft cap so user turns don't stretch.
const USER_BUBBLE_SX = {
  alignSelf: 'flex-end',
  position: 'relative',
  maxWidth: 'min(42rem, 92%)',
  px: 1.25, py: 0.625,
  borderRadius: 1,
  bgcolor: 'action.hover',
};

// AI: full column width (presentation P-05/P-06) — tables/charts need the rail.
// Cap was 42rem and left large empty gutters; Arabic dir=auto still uses plaintext.
const AI_BUBBLE_SX = {
  alignSelf: 'stretch',
  maxWidth: '100%',
  width: '100%',
  px: 1.5, py: 0,
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

// Derive a pending action's true ``kind`` when the ``kind`` tag is missing
// (legacy persisted messages predate the tag). Mirrors the backend
// ``_classify_pending`` so a memory proposal is NEVER rendered as an empty
// "DQ rule" card — anti-fabrication on the render side too.
function derivePendingKind(pending) {
  if (pending?.kind) return pending.kind;
  const tool = String(pending?.tool || '').toLowerCase();
  const operation = String(pending?.operation || '').toLowerCase();
  const method = String(pending?.method || '').toUpperCase();
  if (method === 'MEMORY' || operation === 'learn' || operation === 'forget' ||
      tool === 'learn_fact' || tool === 'forget_fact') {
    return 'memory';
  }
  const proposedRule = pending?.proposed_rule;
  if (proposedRule && typeof proposedRule === 'object' && (proposedRule.name || '').trim()) {
    return 'dq_rule';
  }
  if (method || pending?.endpoint) return 'host';
  return 'dq_rule';
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

// Phase I2-F (RULE_29) — code-sandbox *outputs* (chart / table / value) may
// render in Chat. Sandbox *source* never does (RULE_23 — employees must not
// see engine code). Admin audit / logs remain the place to inspect what ran.

function ChoiceForm({ options, onSubmit }) {
  const { t } = useTranslation('ai');
  const [picked, setPicked] = useState('');
  const [own, setOwn] = useState('');
  const [sent, setSent] = useState(false);
  const labels = options
    .map((option) => String(option?.label || option?.value || '').trim())
    .filter(Boolean);
  const value = own.trim() || picked;
  return (
    <Box sx={{ mt: 1.25 }}>
      <RadioGroup
        value={picked}
        onChange={(event) => {
          setPicked(event.target.value);
          setOwn('');
        }}
      >
        {labels.map((label) => (
          <FormControlLabel
            key={label}
            value={label}
            disabled={sent}
            control={<Radio size="small" />}
            label={<Typography variant="body2">{label}</Typography>}
          />
        ))}
      </RadioGroup>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
        <TextField
          size="small"
          fullWidth
          disabled={sent}
          placeholder={t('choice.own')}
          value={own}
          onChange={(event) => {
            setOwn(event.target.value);
            setPicked('');
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && own.trim() && !sent) {
              event.preventDefault();
              setSent(true);
              onSubmit(own.trim());
            }
          }}
        />
        <Button
          size="small"
          variant="contained"
          disabled={sent || !value}
          onClick={() => {
            setSent(true);
            onSubmit(value);
          }}
        >
          {t('choice.send')}
        </Button>
      </Stack>
    </Box>
  );
}

ChoiceForm.propTypes = {
  options: PropTypes.arrayOf(PropTypes.shape({
    label: PropTypes.string,
    value: PropTypes.string,
  })).isRequired,
  onSubmit: PropTypes.func,
};

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
  onOpenPanel,
  onNotify,
  onStartThreadFromHere,
  onReplyInThread,
  /** Current Ask|Plan dial — hide "Switch to Plan" when already on Plan. */
  composerProcess = 'ask',
}) {
  const { token } = useAuth();
  const [createdPlanId, setCreatedPlanId] = useState('');
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
  const [detailsOpenId, setDetailsOpenId] = useState(null); // execution_id — L1 prep
  const [techOpenId, setTechOpenId] = useState(null); // execution_id — L2 JSON
  const [editAction, setEditAction] = useState(null);       // pending action being edited
  const [editJson, setEditJson] = useState('');
  const [editJsonError, setEditJsonError] = useState('');

  const { t } = useTranslation('ai');

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
  // PAQ-2B — typed AnswerEnvelope (flag-gated OFF by default in the backend).
  // Read defensively from the top-level field or metadata_json, mirroring the
  // code_result pattern. Absent → EnvelopeMessage falls back to raw markdown.
  const envelope = message.envelope || metadata?.envelope || null;

  // 
  // Wave F3-F — planning trace for multi-step assistant turns, surfaced in
  // outcome language (step_label + duration). Read top-level first, then
  // fall back to metadata_json (mirrors confidence/honest-uncertainty reads).
  const toolTrace = message.tool_trace || metadata.tool_trace || [];

  // C2 — calibrated confidence (Faculty 7): read the REAL backend outcome
  // signal off the top-level serialized fields, falling back to metadata_json
  // for robustness (RULE_23 — outcome copy, never raw critic internals).
  const confidenceLevel = message.confidence_label || metadata.confidence_label || '';
  const honestUncertainty = !!(
    message.honest_uncertainty ?? metadata.honest_uncertainty
  );

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
  // PAQ-3A — provenance sources for non-envelope answers: surface the same four
  // facts the envelope chips render (tool, rows_returned, truncated, resolved_at),
  // read defensively from metadata_json / the provenance payload / a top-level field.
  const provenanceSources = normalizeProvenanceSources(
    metadata,
    provenancePayload,
    message.sources,
  );
  // RULE_23 — Chat never renders sandbox/engine code fences to employees.
  // Keep charts/tables via code_result outputs; strip ```python/json dumps
  // from the prose body so they cannot appear as markdown code blocks.
  const operatorContent = isUser
    ? message.content
    : (splitAnswerAppendix(message.content).prose || message.content);
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
  const showProvenance = !isUser && (hasStructured || hasScope || provenanceSources.length > 0);

  // Honest-uncertainty turns get a distinct calm left accent (PULSE-UX §2.7) —
  // a quiet "here's my best read" marker, NOT an error treatment.
  const bubbleSx = isUser
    ? USER_BUBBLE_SX
    : {
        ...AI_BUBBLE_SX,
        ...(honestUncertainty && {
          borderInlineStart: '2px solid',
          borderColor: 'warning.light',
          ps: 1.5,
        }),
      };

  // When feedback is given, the clicked thumb gets a light color: green up
  // for accepted, red down for rejected. No text, no extra row.
  const outcomeTint =
    message.outcome === 'accepted' ? 'rgba(46, 125, 50, 0.10)' : message.outcome === 'rejected' ? 'rgba(211, 47, 47, 0.10)' : undefined;
  const outcomeFg =
    message.outcome === 'accepted' ? 'success.main' : message.outcome === 'rejected' ? 'error.main' : undefined;
  const showFeedback =
    !isUser && (message.outcome || onAccept || onReject || onCorrect || onPromote || onRetry || onDelete);

  const renderStructuredContent = () => {
    // Phase I2-F (RULE_29): code_result messages carry no ``type`` (the
    // backend stores the sandbox result directly, not under a structured
    // type), so only the user guard short-circuits here. Type-less messages
    // with no code_result still fall through to the end ``return null``
    // (zero regression).
    if (isUser) return null;

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
                    <SuggestionDiff suggestion={s} />
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

    // Phase I2-F (RULE_29) — code-sandbox result rendering. Read the executed
    // code_result defensively from the top-level field or metadata_json; the
    // backend has already run the sandbox (nothing is re-fetched here).
    const codeResult = message.code_result || message.metadata_json?.code_result;
    // Prefer Answer Envelope Chart.js / Mermaid over sandbox matplotlib PNG.
    const envelopeHasCharts = Array.isArray(envelope?.charts) && envelope.charts.length > 0;
    const proseHasMermaid = typeof operatorContent === 'string'
      && operatorContent.includes('```mermaid');
    if (codeResult) {
      const errorText = typeof codeResult.error === 'string' ? codeResult.error.trim() : '';
      if (errorText) {
        return (
          <Box sx={{ mt: 1 }}>
            <Alert severity="warning" role="alert">
              {errorText}
            </Alert>
          </Box>
        );
      }

      const hasTable = Array.isArray(codeResult.table_rows) && codeResult.table_rows.length > 0;
      const hasResult = codeResult.result != null && codeResult.result !== '';
      const showSandboxImage = Boolean(codeResult.image_b64)
        && !envelopeHasCharts
        && !proseHasMermaid;
      if (!showSandboxImage && !hasTable && !hasResult) {
        return null;
      }

      return (
        <Box sx={{ mt: 1 }}>
          {showSandboxImage ? (
            <Box dir="ltr">
              <img
                src={`data:image/png;base64,${codeResult.image_b64}`}
                alt={t('generatedChart')}
                loading="lazy"
                style={{ maxWidth: '100%', borderRadius: 8 }}
              />
            </Box>
          ) : hasTable ? (
            <Box dir="ltr">
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
                    rows={toGridRows(codeResult.table_rows)}
                    columns={toGridColumns(codeResult.table_rows, null)}
                    density="compact"
                    hideFooter={codeResult.table_rows.length <= 25}
                    getRowId={(row) => row.id}
                    emptyMessage="No rows returned"
                  />
                </Suspense>
              </Box>
              <Typography variant="caption" color="text.secondary">
                {codeResult.table_rows.length} rows
              </Typography>
            </Box>
          ) : (
            <KeyValueOutput value={{ result: codeResult.result }} />
          )}
          {/* RULE_23 — never surface sandbox source in Chat. Charts / tables /
              images above are the employee deliverable; code stays off-UI. */}
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
  // download action → a generated file (Word/Excel) the user can download.
  const downloadActions = rawActions.filter((a) => a?.type === 'download');
  // open_panel action → switch the workspace to a panel (e.g. Tasks) and
  // focus the referenced object (plan created from chat). Rendered as a
  // button (NOT a route Link — the panel is a workspace surface).
  // Panel=plan is the Ask→Plan dial CTA — hide it when already on Plan.
  const panelActions = rawActions.filter((a) => {
    if (a?.type !== 'open_panel') return false;
    if (a.panel === 'plan' && composerProcess === 'plan') return false;
    return true;
  });
  const pendingActions = Array.isArray(metadata.pending_actions) ? metadata.pending_actions : [];
  const showActionRow = Boolean(
    !isUser && (
      navigateActions.length > 0 || downloadActions.length > 0 ||
      pendingActions.length > 0 || panelActions.length > 0
    ),
  );

  // ── Pending-action proposal review ────────────────────────────────────
  // Confirm / Decline + L1 "How this was prepared" + nested L2 technical JSON.
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
        // Derive the true kind (memory / dq_rule / host) — legacy messages
        // without the ``kind`` tag are re-classified from tool/operation so a
        // memory proposal never renders as an empty "DQ rule" card.
        const kind = derivePendingKind(pending);
        const isMemory = kind === 'memory';
        const proposed = pending.proposed_rule || {};
        const proposedName = isMemory
          ? pending.confirmation_message || 'this memory'
          : proposed.name || pending.confirmation_message || 'this proposal';
        const detailsOpen = detailsOpenId === executionId;
        const techOpen = techOpenId === executionId;
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
        const confirmLabel = isMemory
          ? (pending.operation === 'forget' ? 'Confirm & forget' : 'Confirm & remember')
          : kind === 'host'
            ? 'Confirm & run'
            : 'Confirm & create';
        // Screen-reader wording ("and") differs from the visible "&" for
        // clarity; existing tests match the accessible name.
        const confirmAriaLabel = isMemory
          ? (pending.operation === 'forget' ? 'Confirm and forget' : 'Confirm and remember')
          : kind === 'host'
            ? 'Confirm and run'
            : 'Confirm and create';
        return (
          <Paper key={executionId} variant="outlined" sx={{ p: 1.25 }}>
            <Stack spacing={1}>
              <Stack direction="row" flexWrap="wrap" gap={0.5}>
                {/* Memory proposals (learn/forget) are personal, user-requested
                    writes — confirmable in Chat mode. System mutations
                    (DQ rule / host) stay gated behind Agent mode. */}
                {executeMode || isMemory ? (
                  <>
                    <Button
                      size="small"
                      color="success"
                      variant="outlined"
                      disabled={!onConfirmExecution}
                      onClick={() => onConfirmExecution?.(executionId, pending)}
                      aria-label={`${confirmAriaLabel} ${proposedName}`}
                    >
                      {confirmLabel}
                    </Button>
                    {!isMemory && (
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
                    )}
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
                  onClick={() => {
                    setDetailsOpenId(detailsOpen ? null : executionId);
                    if (detailsOpen) setTechOpenId(null);
                  }}
                  aria-expanded={detailsOpen}
                  aria-label={`${presentConsentExpandLabel({ open: detailsOpen })} for ${proposedName}`}
                >
                  {presentConsentExpandLabel({ open: detailsOpen })}
                </Button>
              </Stack>

              {detailsOpen && (
                <Stack spacing={1} sx={{ pt: 0.5 }} data-testid="consent-prep-details">
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    {pending.confirmation_message || `Create DQ rule "${proposedName}"?`}
                  </Typography>
                  {isMemory && pending.category ? (
                    <Typography variant="caption" color="text.secondary">
                      Category: {pending.category}
                    </Typography>
                  ) : null}
                  {!isMemory && validation?.passed === false && Array.isArray(validation.errors) && (
                    <Typography variant="caption" color="error">
                      {validation.errors.join(' · ')}
                    </Typography>
                  )}
                  <Button
                    size="small"
                    variant="text"
                    onClick={() => setTechOpenId(techOpen ? null : executionId)}
                    aria-expanded={techOpen}
                    sx={{ alignSelf: 'flex-start', px: 0, minWidth: 0 }}
                  >
                    {presentTechnicalDetailsLabel({ open: techOpen })}
                  </Button>
                  {techOpen && (
                    <Stack spacing={1} data-testid="consent-tech-details">
                      {isMemory ? (
                        jsonBlock('Fact', pending.fact || pending.confirmation_message || '')
                      ) : (
                        <>
                          <Chip
                            size="small"
                            variant="outlined"
                            color={validationColor}
                            label={validationLabel}
                            sx={{ alignSelf: 'flex-start' }}
                          />
                          {kind !== 'host' && jsonBlock('Proposed rule (definition JSON)', JSON.stringify(proposed, null, 2))}
                          {jsonBlock(
                            'Body that will be POSTed',
                            JSON.stringify(pending.proposed_body || pending.body || {}, null, 2),
                          )}
                        </>
                      )}
                    </Stack>
                  )}
                </Stack>
              )}
            </Stack>
          </Paper>
        );
      })}
      {panelActions.length > 0 && (
        <Box
          data-testid="message-panel-actions"
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 0.75,
            alignSelf: 'stretch',
            justifyContent: 'flex-start',
          }}
          dir="auto"
        >
          {panelActions.map((act, idx) => (
            <Button
              key={`${act.panel}-${act.plan_id || ''}-${idx}`}
              size="small"
              variant={panelActions.length === 1 && navigateActions.length === 0 ? 'contained' : (idx === 0 ? 'contained' : 'outlined')}
              disabled={!onOpenPanel}
              onClick={() => onOpenPanel?.(act.panel, act.plan_id, {
                processHint: act.process_hint || metadata.process_hint || '',
                draft: metadata.draft || act.summary || '',
                // Chat proposes, Agent applies: a refined plan brief travels
                // with the CTA and is applied via replan + diff review in Tasks.
                revision: typeof act.revision === 'string' ? act.revision : '',
              })}
              aria-label={act.label || 'Open'}
            >
              {act.label || 'Open'}
            </Button>
          ))}
        </Box>
      )}
      {navigateActions.length > 0 && (
        <Box
          data-testid="message-navigate-actions"
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 0.75,
            // Sit with the reply column (not a full-rail flex-start island).
            alignSelf: 'stretch',
            justifyContent: 'flex-start',
          }}
          dir="auto"
        >
          {navigateActions.map((nav, idx) => (
            <Button
              key={`${nav.route}-${idx}`}
              size="small"
              variant={navigateActions.length === 1 && panelActions.length === 0 ? 'contained' : 'outlined'}
              component={Link}
              to={nav.route}
              aria-label={nav.label || 'Open'}
            >
              {nav.label || 'Open'}
            </Button>
          ))}
        </Box>
      )}
      {downloadActions.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
          {downloadActions.map((dl, idx) => {
            const href = resolveBackendUrl(dl.path);
            return (
              <Button
                key={`${dl.filename || dl.path}-${idx}`}
                size="small"
                variant={downloadActions.length === 1 ? 'contained' : 'outlined'}
                component="a"
                href={href}
                download={dl.filename || true}
                target="_blank"
                rel="noreferrer noopener"
                startIcon={<DownloadIcon sx={{ fontSize: 16 }} />}
                aria-label={dl.label || 'Download'}
              >
                {dl.label || 'Download'}
              </Button>
            );
          })}
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
      {/* D3 — "why this answer" provenance (on-click, not hover) */}
      {!isUser && showProvenance && (
        <ReasoningTrace
          lines={provenanceLines}
          actions={navigateActions}
          pendingActions={pendingActions}
          createdAt={message.created_at}
          externalSources={message.external_sources || provenancePayload?.external_sources || []}
          sources={provenanceSources}
          toolTrace={toolTrace}
        />
      )}

      <Box sx={bubbleSx}>
        {/* Wave F3-F — collapsible "Considered: …" planning pill above the answer body */}
        {!isUser && <PlanningHeader trace={toolTrace} />}

        {/* status chip only on error/interrupted — inline, no row */}
        {!isUser && statusLabel && (
          <Chip size="small" color={statusColor} label={statusLabel} sx={{ height: 14, mb: 0.5, '& .MuiChip-label': { px: 0.5, fontSize: '0.6rem' } }} />
        )}

        {/* D3 — AI-authored label (quiet token, never for user messages) */}
        {!isUser && (
          <Box sx={{ mb: 0.5 }}>
            <AIGeneratedBadge />
          </Box>
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
                inputProps={{ dir: 'auto' }}
                sx={{ '& textarea': { unicodeBidi: 'plaintext' } }}
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
            <>
              <Typography
                variant="body2"
                dir="auto"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: 1.5,
                  color: 'text.primary',
                  unicodeBidi: 'plaintext',
                }}
              >
                {message.content}
              </Typography>
            </>
          )
        ) : (
          <LongContent content={operatorContent}>
            <Box
              ref={contentRef}
              data-testid="message-content"
              dir="auto"
              sx={{ color: 'text.primary', unicodeBidi: 'plaintext' }}
            >
              <EnvelopeMessage envelope={envelope} fallbackContent={operatorContent} />
            </Box>
          </LongContent>
        )}

        {structuredContent}

        {/* C2 — calibrated confidence (Faculty 7): subtle inline indicator.
            Renders a bar (high/medium/low) or a calm honest-uncertainty caption. */}
        {!isUser && (confidenceLevel || honestUncertainty) && (
          <Box sx={{ mt: 0.5 }}>
            <ConfidenceIndicator label={confidenceLevel} honest={honestUncertainty} />
          </Box>
        )}

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
              label={t('correction.label')}
              value={correctionText}
              onChange={(event) => setCorrectionText(event.target.value)}
              placeholder={t('correction.placeholder')}
            />
            <Stack direction="row" spacing={0.5}>
              <Button
                size="small"
                variant="outlined"
                disabled={!correctionText.trim()}
                onClick={() => onCorrect?.(message, correctionText.trim())}
              >
                {t('correction.save')}
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => {
                  setCorrectionOpen(false);
                  setCorrectionText('');
                }}
              >
                {t('correction.cancel')}
              </Button>
            </Stack>
          </Box>
        )}

        {/* Usage + time-ago metadata now live on the hover action row below. */}

        {metadata.form?.kind === 'choice' && metadata.form.options?.length >= 2 && (
          <ChoiceForm
            options={metadata.form.options}
            onSubmit={(value) => onFollowUp?.(value)}
          />
        )}

        {metadata.form?.kind === 'plan_proposal' && (
          <PlanProposalForm
            proposal={metadata.form}
            onCreate={metadata.form.conversation_id ? async () => {
              const plan = await commitPlanProposal(token, metadata.form.conversation_id);
              setCreatedPlanId(plan?.id || '');
            } : undefined}
            onChange={(text) => onFollowUp?.(text)}
            onOpenTasks={onOpenPanel && createdPlanId
              ? () => onOpenPanel('tasks', createdPlanId, {})
              : undefined}
          />
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
          {(onCorrect || onPromote || onRetry || onDelete || onStartThreadFromHere || onReplyInThread) && (
            <>
              <Tooltip title="More actions">
                <IconButton size="small" onClick={(e) => setMoreMenuAnchor(e.currentTarget)} aria-label="More message actions" sx={{ p: 0.5 }}>
                  <MoreVertIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
              <Menu anchorEl={moreMenuAnchor} open={Boolean(moreMenuAnchor)} onClose={() => setMoreMenuAnchor(null)}>
                {onStartThreadFromHere && message.id && !String(message.id).startsWith('local-') && message.id !== 'streaming' && (
                  <MenuItem
                    onClick={() => { onStartThreadFromHere(message); setMoreMenuAnchor(null); }}
                    sx={{ fontSize: '0.8125rem' }}
                    data-testid="message-start-thread"
                  >
                    {t('threadFromHere')}
                  </MenuItem>
                )}
                {onReplyInThread && message.id && !String(message.id).startsWith('local-') && (
                  <MenuItem
                    onClick={() => { onReplyInThread(message); setMoreMenuAnchor(null); }}
                    sx={{ fontSize: '0.8125rem' }}
                    data-testid="message-reply-in-thread"
                  >
                    {t('replyInThread')}
                  </MenuItem>
                )}
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

      {isUser && !editOpen && (
        <Box
          data-testid="user-message-actions-row"
          sx={{
            height: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 0.25,
            alignSelf: 'flex-end',
          }}
        >
          <Tooltip title={copied ? 'Copied' : 'Copy'}>
            <IconButton size="small" onClick={handleCopyPlain} aria-label="Copy message" sx={{ p: 0.5 }}>
              {copied ? <CheckIcon sx={{ fontSize: 14 }} /> : <ContentCopyIcon sx={{ fontSize: 14 }} />}
            </IconButton>
          </Tooltip>
          {(onEdit || onDelete || onStartThreadFromHere || onReplyInThread) && (
            <>
              <Tooltip title="More actions">
                <IconButton size="small" onClick={(e) => setMoreMenuAnchor(e.currentTarget)} aria-label="More message actions" sx={{ p: 0.5 }}>
                  <MoreVertIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
              <Menu anchorEl={moreMenuAnchor} open={Boolean(moreMenuAnchor)} onClose={() => setMoreMenuAnchor(null)}>
                {onStartThreadFromHere && message.id && !String(message.id).startsWith('local-') && (
                  <MenuItem
                    onClick={() => { onStartThreadFromHere(message); setMoreMenuAnchor(null); }}
                    sx={{ fontSize: '0.8125rem' }}
                    data-testid="message-start-thread"
                  >
                    {t('threadFromHere')}
                  </MenuItem>
                )}
                {onReplyInThread && message.id && !String(message.id).startsWith('local-') && (
                  <MenuItem
                    onClick={() => { onReplyInThread(message); setMoreMenuAnchor(null); }}
                    sx={{ fontSize: '0.8125rem' }}
                    data-testid="message-reply-in-thread"
                  >
                    {t('replyInThread')}
                  </MenuItem>
                )}
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
    confidence_label: PropTypes.string,
    honest_uncertainty: PropTypes.bool,
    tool_trace: PropTypes.array,
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
  onStartThreadFromHere: PropTypes.func,
  onReplyInThread: PropTypes.func,
  composerProcess: PropTypes.oneOf(['ask', 'plan']),
};

export default AIMessageBubble;
