// src/apps/my/components/WorkflowGraph.jsx
// Presentational — horizontal node-edge DAG for the approver chain.
// One node per `approver_chain` step (ordered by `order`) plus a terminal
// "Completed" node. Node color encodes state, but every node ALSO carries
// text (role / intent / decision chip), so the graph is never color-only.
// Pure function of props (React.memo, no effects, no fetch). RTL mirrors the
// flow arrows via theme.direction.
import React, { Fragment, memo, useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Card, CardContent, Chip, Stack, Typography, useTheme } from '@mui/material';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import { useTranslation } from 'react-i18next';
import { SectionTitle } from './myRequestsCommon';
import { codeLabel, ROLE_SUFFIX, INTENT_SUFFIX } from './myRequestsLabels';
import { useIsMobile } from '../../../hooks/useIsMobile';
import { FONT } from '../../../theme/themeTokens';

/**
 * Node state → theme color token (RULE_8 — never raw hex), MUI Chip color,
 * and localized label key. `skipped_auto` = auto-approve / empty-approver
 * steps; `skipped_condition` = condition-failed steps (visibly distinct from
 * approved/rejected, and labelled in TEXT — never color-only).
 */
const STATE_META = {
  current: { color: 'primary.main', chip: 'primary', label: 'graphNodeCurrent' },
  approved: { color: 'success.main', chip: 'success', label: 'graphNodeApproved' },
  acknowledged: { color: 'info.main', chip: 'info', label: 'graphNodeAcknowledged' },
  reviewed: { color: 'secondary.main', chip: 'secondary', label: 'graphNodeReviewed' },
  rejected: { color: 'error.main', chip: 'error', label: 'graphNodeRejected' },
  sent_back: { color: 'warning.main', chip: 'warning', label: 'graphNodeSentBack' },
  skipped_auto: { color: 'text.disabled', chip: 'default', label: 'graphNodeSkippedAuto' },
  skipped_condition: { color: 'text.disabled', chip: 'default', label: 'graphNodeSkippedCondition' },
  pending: { color: 'text.disabled', chip: 'default', label: 'graphNodePending' },
};

/** Canonical display order for the legend (matches flow progression). */
const STATE_ORDER = [
  'current',
  'approved',
  'acknowledged',
  'reviewed',
  'rejected',
  'sent_back',
  'skipped_auto',
  'skipped_condition',
  'pending',
];

/** Resolve a `palette` token path (e.g. "success.main") to a concrete color. */
function tokenColor(theme, token) {
  if (!token || typeof token !== 'string') return theme.palette.text.disabled;
  const value = token.split('.').reduce((acc, part) => (acc == null ? acc : acc[part]), theme.palette);
  return value || theme.palette.text.disabled;
}

/** Derive a node state from a chain step + the current step index. */
function stepState(step, order, currentStep) {
  const decision = step?.decision;
  if (decision === 'skip') return 'skipped_condition';
  if (decision === 'auto') return 'skipped_auto';
  if (decision === 'approved') return 'approved';
  if (decision === 'acknowledged') return 'acknowledged';
  if (decision === 'reviewed') return 'reviewed';
  if (decision === 'rejected') return 'rejected';
  if (decision === 'sent_back') return 'sent_back';
  if (currentStep != null && Number(order) === Number(currentStep)) return 'current';
  return 'pending';
}

/** Terminal "Completed" node is reached only when the flow approved. */
function terminalState(status) {
  return status === 'approved' ? 'approved' : 'pending';
}

/** Horizontal arrow connector (SVG). Flips direction under RTL. */
function FlowArrow({ rtl }) {
  return (
    <Box
      aria-hidden="true"
      sx={{ flexShrink: 0, px: 0.5, alignSelf: 'center', color: 'text.disabled' }}
    >
      <svg
        width="18"
        height="12"
        viewBox="0 0 18 12"
        focusable="false"
        style={{ display: 'block', transform: rtl ? 'scaleX(-1)' : undefined }}
      >
        <line x1="0" y1="6" x2="14" y2="6" stroke="currentColor" strokeWidth="1.5" />
        <polygon points="14,2 18,6 14,10" fill="currentColor" />
      </svg>
    </Box>
  );
}

FlowArrow.propTypes = {
  rtl: PropTypes.bool,
};

FlowArrow.defaultProps = {
  rtl: false,
};

/** One workflow node — a focusable button with role/intent/decision text. */
function NodeBox({ node, meta, color, filled, fullWidth }) {
  const muted = node.state === 'pending' || node.state === 'skipped_auto' || node.state === 'skipped_condition';
  return (
    <Box
      component="button"
      type="button"
      tabIndex={0}
      aria-label={node.ariaLabel}
      aria-current={node.state === 'current' ? 'step' : undefined}
      sx={{
        flexShrink: 0,
        width: fullWidth ? '100%' : 150,
        minHeight: 76,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        textAlign: 'start',
        gap: 0.5,
        p: 1,
        bgcolor: filled ? 'primary.main' : 'background.paper',
        color: filled ? 'primary.contrastText' : 'text.primary',
        border: '1px solid',
        borderColor: filled ? 'primary.main' : muted ? 'divider' : color,
        borderInlineStart: '4px solid',
        borderInlineStartColor: color,
        borderRadius: 1.5,
        cursor: 'default',
        '&:hover': { bgcolor: filled ? 'primary.dark' : 'action.hover' },
        '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 2 },
      }}
    >
      <Typography sx={{ ...FONT.body2, fontWeight: 600, lineHeight: 1.3, color: 'inherit' }} noWrap>
        {node.role}
      </Typography>
      {node.intent ? (
        <Typography
          sx={{
            ...FONT.bodySmall,
            lineHeight: 1.3,
            color: filled ? 'primary.contrastText' : 'text.secondary',
            opacity: filled ? 0.85 : 1,
          }}
          noWrap
        >
          {node.intent}
        </Typography>
      ) : null}
      <Chip
        size="small"
        variant="outlined"
        color={filled ? 'default' : meta.chip}
        label={node.stateLabel}
        sx={{
          alignSelf: 'flex-start',
          height: 16,
          fontSize: '0.5625rem',
          '& .MuiChip-label': { px: 0.75 },
          ...(filled ? { color: 'primary.contrastText', borderColor: 'primary.contrastText' } : {}),
        }}
      />
      {node.metaText ? (
        <Typography
          sx={{
            ...FONT.bodySmall,
            lineHeight: 1.3,
            color: filled ? 'primary.contrastText' : 'text.secondary',
            opacity: filled ? 0.85 : 1,
          }}
          noWrap
        >
          {node.metaText}
        </Typography>
      ) : null}
    </Box>
  );
}

NodeBox.propTypes = {
  node: PropTypes.shape({
    state: PropTypes.string.isRequired,
    role: PropTypes.string.isRequired,
    intent: PropTypes.string,
    stateLabel: PropTypes.string.isRequired,
    metaText: PropTypes.string,
    ariaLabel: PropTypes.string.isRequired,
  }).isRequired,
  meta: PropTypes.object.isRequired,
  color: PropTypes.string,
  filled: PropTypes.bool.isRequired,
  fullWidth: PropTypes.bool,
};

NodeBox.defaultProps = {
  fullWidth: false,
};

/**
 * Approver-chain workflow graph.
 * @param {Array} props.chain - `approver_chain` from the detail serializer
 * @param {number} [props.currentStep] - `current_step` index
 * @param {string} [props.status] - correspondence status (for the terminal node)
 */
function WorkflowGraph({ chain, currentStep, status }) {
  const { t } = useTranslation('my');
  const theme = useTheme();
  const isRtl = theme.direction === 'rtl';
  const isMobile = useIsMobile();

  const steps = useMemo(() => {
    const list = Array.isArray(chain) ? chain : [];
    return [...list].sort((a, b) => Number(a.order ?? 0) - Number(b.order ?? 0));
  }, [chain]);

  const nodes = useMemo(() => {
    if (steps.length === 0) return [];
    const built = steps.map((step, index) => {
      const order = Number(step.order ?? 0);
      const state = stepState(step, order, currentStep);
      const role = codeLabel(t, 'role', ROLE_SUFFIX, step.role);
      const intent = codeLabel(t, 'intent', INTENT_SUFFIX, step.intent);
      const stateLabel = t(STATE_META[state].label);
      const approverCount = Array.isArray(step.user_ids) ? step.user_ids.length : 0;
      const isSkipped = state === 'skipped_auto' || state === 'skipped_condition';
      return {
        key: `step-${index}`,
        state,
        role,
        intent,
        stateLabel,
        metaText: isSkipped ? null : t('stepperApprovers', { count: approverCount }),
        ariaLabel: `${role} — ${intent} — ${stateLabel}`,
      };
    });
    const terminal = terminalState(status);
    built.push({
      key: 'terminal',
      state: terminal,
      role: t('graphNodeCompleted'),
      intent: '',
      stateLabel: t(STATE_META[terminal].label),
      metaText: null,
      ariaLabel: `${t('graphNodeCompleted')} — ${t(STATE_META[terminal].label)}`,
    });
    return built;
  }, [steps, currentStep, status, t]);

  const legendStates = useMemo(() => {
    const present = new Set(nodes.map((n) => n.state));
    return STATE_ORDER.filter((s) => present.has(s));
  }, [nodes]);

  return (
    <Card variant="outlined" data-testid="workflow-graph">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={AccountTreeIcon} title={t('graphTitle')} />
        {nodes.length === 0 ? (
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>{t('graphEmpty')}</Typography>
        ) : isMobile ? (
          <Stack role="group" aria-label={t('graphTitle')} spacing={1}>
            {nodes.map((node) => {
              const meta = STATE_META[node.state];
              const color = tokenColor(theme, meta.color);
              return (
                <NodeBox
                  key={node.key}
                  node={node}
                  meta={meta}
                  color={color}
                  filled={node.state === 'current'}
                  fullWidth
                />
              );
            })}
          </Stack>
        ) : (
          <Box role="group" aria-label={t('graphTitle')} sx={{ overflowX: 'auto', pb: 0.5 }}>
            <Stack direction="row" alignItems="center" sx={{ minWidth: 'max-content' }}>
              {nodes.map((node, index) => {
                const meta = STATE_META[node.state];
                const color = tokenColor(theme, meta.color);
                return (
                  <Fragment key={node.key}>
                    {index > 0 ? <FlowArrow rtl={isRtl} /> : null}
                    <NodeBox
                      node={node}
                      meta={meta}
                      color={color}
                      filled={node.state === 'current'}
                    />
                  </Fragment>
                );
              })}
            </Stack>
          </Box>
        )}
        {legendStates.length > 0 ? (
          <Box sx={{ mt: 1 }}>
            <Typography
              sx={{
                ...FONT.bodySmall,
                color: 'text.secondary',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                mb: 0.5,
              }}
            >
              {t('graphLegend')}
            </Typography>
            <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
              {legendStates.map((state) => (
                <Stack key={state} direction="row" alignItems="center" spacing={0.5}>
                  <Box
                    aria-hidden="true"
                    sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: tokenColor(theme, STATE_META[state].color) }}
                  />
                  <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>
                    {t(STATE_META[state].label)}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Box>
        ) : null}
      </CardContent>
    </Card>
  );
}

WorkflowGraph.propTypes = {
  chain: PropTypes.array,
  currentStep: PropTypes.number,
  status: PropTypes.string,
};

WorkflowGraph.defaultProps = {
  chain: [],
  currentStep: null,
  status: null,
};

export default memo(WorkflowGraph);
