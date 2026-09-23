// src/shell/AgentCockpit.jsx
// ADR-0043 — presentational run-cockpit shell: Plan · Run · Canvas · Output
// (exclusive heroes). Parent owns state/handlers; this is pure layout (RULE_2).
import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import MapOutlinedIcon from '@mui/icons-material/MapOutlined';
import ArticleOutlinedIcon from '@mui/icons-material/ArticleOutlined';
import { useTranslation } from 'react-i18next';
import InheritedContextPanel from './InheritedContextPanel';

const SEGMENTS = [
  { value: 'plan', labelKey: 'cockpitPlan', icon: AccountTreeOutlinedIcon },
  { value: 'run', labelKey: 'cockpitRun', icon: PlayCircleOutlineIcon },
  { value: 'canvas', labelKey: 'cockpitCanvas', icon: MapOutlinedIcon },
  { value: 'output', labelKey: 'cockpitOutput', icon: ArticleOutlinedIcon },
];

/**
 * Run-cockpit layout shell.
 * @param {object} props
 * @param {'plan'|'run'|'canvas'|'output'} props.segment
 * @param {function} props.onSegment
 * @param {React.ReactNode} props.header
 * @param {object|null} props.plan
 * @param {function} props.renderPlan
 * @param {function} props.renderRun
 * @param {function} props.renderCanvas
 * @param {function} props.renderOutput
 * @param {React.ReactNode} [props.toolbar] — segment toolbar under tabs (e.g. Plan chrome)
 */
function AgentCockpit({
  segment,
  onSegment,
  header,
  plan,
  renderPlan,
  renderRun,
  renderCanvas,
  renderOutput,
  toolbar = null,
}) {
  const { t } = useTranslation('ai');

  const heroTestId = {
    plan: 'agent-cockpit-hero-plan',
    run: 'agent-cockpit-hero-run',
    canvas: 'agent-cockpit-hero-canvas',
    output: 'agent-cockpit-hero-output',
  }[segment] || 'agent-cockpit-hero-run';

  const body = () => {
    switch (segment) {
      case 'plan':
        return renderPlan();
      case 'canvas':
        return renderCanvas();
      case 'output':
        return renderOutput();
      case 'run':
      default:
        return renderRun();
    }
  };

  return (
    <Box
      data-testid="agent-cockpit"
      data-plan-id={plan?.id ?? ''}
      data-segment={segment}
      sx={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, minHeight: 0 }}
    >
      {header ? (
        <Stack
          direction="row"
          alignItems="center"
          spacing={1}
          sx={{ px: 1, py: 0.5, borderBottom: 1, borderColor: 'divider' }}
        >
          <Box sx={{ flex: 1, minWidth: 0 }}>{header}</Box>
        </Stack>
      ) : null}

      <Box sx={{ px: 1, py: 0.5, borderBottom: 1, borderColor: 'divider' }}>
        <ToggleButtonGroup
          value={segment}
          exclusive
          size="small"
          fullWidth
          onChange={(_e, next) => { if (next) onSegment?.(next); }}
          aria-label={t('cockpitView')}
        >
          {SEGMENTS.map(({ value, labelKey, icon: Icon }) => (
            <ToggleButton
              key={value}
              value={value}
              aria-label={t(labelKey)}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', py: 0.25, gap: 0.5 }}
            >
              <Icon sx={{ fontSize: 14 }} />
              {t(labelKey)}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {toolbar ? (
        <Box
          data-testid="agent-cockpit-toolbar"
          sx={{ px: 1, py: 0.75, borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}
        >
          {toolbar}
        </Box>
      ) : null}

      <Box
        sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}
        data-testid="cockpit-body"
        data-hero={segment}
      >
        <Box data-testid={heroTestId}>
          <Box sx={{ mb: 1 }}>
            <InheritedContextPanel plan={plan} />
          </Box>
          {body()}
        </Box>
      </Box>
    </Box>
  );
}

AgentCockpit.propTypes = {
  segment: PropTypes.oneOf(['plan', 'run', 'canvas', 'output']).isRequired,
  onSegment: PropTypes.func.isRequired,
  header: PropTypes.node,
  plan: PropTypes.object,
  renderPlan: PropTypes.func.isRequired,
  renderRun: PropTypes.func.isRequired,
  renderCanvas: PropTypes.func.isRequired,
  renderOutput: PropTypes.func.isRequired,
  toolbar: PropTypes.node,
};

export default AgentCockpit;

/** Soft lifecycle default (ADR-0043 §2). */
export function defaultCockpitSegment(effectiveStatus, phase) {
  // Settled session phases win so Output can show stop/fail chrome —
  // but never treat a false "finished" as Output when the plan is not
  // actually settled (Completed + 0/N pending).
  if (phase === 'stopped' || phase === 'error') {
    return 'output';
  }
  if (phase === 'finished') {
    if (
      effectiveStatus === 'completed'
      || effectiveStatus === 'completed_with_gaps'
      || effectiveStatus === 'failed'
    ) {
      return 'output';
    }
    return 'run';
  }
  if (effectiveStatus === 'pending_approval' || effectiveStatus === 'discovering') {
    return 'plan';
  }
  if (
    phase === 'working'
    || phase === 'paused'
    || effectiveStatus === 'running'
    || effectiveStatus === 'paused'
    || effectiveStatus === 'approved'
  ) {
    return 'run';
  }
  if (
    effectiveStatus === 'completed'
    || effectiveStatus === 'completed_with_gaps'
    || effectiveStatus === 'failed'
  ) {
    return 'output';
  }
  // Declined before a run — Plan shows “nothing executed”.
  if (effectiveStatus === 'cancelled') return 'plan';
  return 'plan';
}

/** Migrate ADR-0034 segment ids → ADR-0043. */
export function normalizeCockpitSegment(raw) {
  if (raw === 'steps') return 'run';
  if (raw === 'metrics') return 'output';
  if (raw === 'plan' || raw === 'run' || raw === 'canvas' || raw === 'output') return raw;
  return 'run';
}
