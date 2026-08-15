// src/shell/AIMessageBubble.jsx
import React, { Suspense, lazy, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, Paper, Stack, TextField, Tooltip, Typography } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from '../utils/dateUtils';

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

function AIMessageBubble({
  message,
  onAcceptSuggestion,
  onRejectSuggestion,
  canManageRules = true,
  onAccept,
  onReject,
  onCorrect,
}) {
  const [showTimestamp, setShowTimestamp] = useState(false);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionText, setCorrectionText] = useState('');
  const isUser = message.role === 'user';
  const metadata = normalizeMetadata(message);
  const followUps = metadata.follow_up_questions || [];

  const bubbleSx = isUser ? USER_BUBBLE_SX : AI_BUBBLE_SX;
  const Icon = isUser ? PersonIcon : SmartToyIcon;

  const outcomeLabel = OUTCOME_LABELS[message.outcome] || message.outcome;
  const outcomeColor =
    message.outcome === 'accepted' ? 'success' : message.outcome === 'rejected' ? 'error' : 'default';
  const showFeedback = !isUser && (message.outcome || onAccept || onReject || onCorrect);

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
              <Stack direction="row" spacing={0.5}>
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
              </Stack>
            )}
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
    outcome: PropTypes.string,
    correction_text: PropTypes.string,
  }).isRequired,
  onAcceptSuggestion: PropTypes.func,
  onRejectSuggestion: PropTypes.func,
  canManageRules: PropTypes.bool,
  onAccept: PropTypes.func,
  onReject: PropTypes.func,
  onCorrect: PropTypes.func,
};

export default AIMessageBubble;
