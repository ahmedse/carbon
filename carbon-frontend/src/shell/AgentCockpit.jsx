// src/shell/AgentCockpit.jsx
// Task screens: Now · Picture · Result (Result only after an outcome).
// Journey is a fold under Result, not a fourth tab. Parent owns state.
import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import InheritedContextPanel from './InheritedContextPanel';
import { hasTaskOutcome } from './taskWorkspace';

const SEGMENTS = [
  { value: 'run', labelKey: 'cockpitNow' },
  { value: 'plan', labelKey: 'cockpitPicture' },
  { value: 'output', labelKey: 'cockpitResult', needsOutcome: true },
];

/**
 * Run-cockpit layout shell.
 * @param {object} props
 * @param {'plan'|'run'|'canvas'|'output'} props.segment
 * @param {function} props.onSegment
 * @param {React.ReactNode} props.header
 * @param {React.ReactNode} [props.line]
 * @param {object|null} props.plan
 * @param {function} props.renderPlan
 * @param {function} props.renderRun
 * @param {function} props.renderCanvas
 * @param {function} props.renderOutput
 * @param {React.ReactNode} [props.toolbar]
 * @param {boolean} [props.resultReady]
 */
function AgentCockpit({
  segment,
  onSegment,
  header,
  line = null,
  plan,
  renderPlan,
  renderRun,
  renderCanvas,
  renderOutput,
  toolbar = null,
  resultReady = false,
}) {
  const { t } = useTranslation('ai');

  const visible = resultReady ? segment : (segment === 'output' ? 'run' : segment);
  const view = visible === 'canvas' ? 'plan' : visible;

  const heroTestId = {
    plan: 'agent-cockpit-hero-plan',
    run: 'agent-cockpit-hero-run',
    canvas: 'agent-cockpit-hero-plan',
    output: 'agent-cockpit-hero-output',
  }[view] || 'agent-cockpit-hero-run';

  const body = () => {
    switch (view) {
      case 'plan':
        return renderPlan();
      case 'canvas':
        return renderCanvas ? renderCanvas() : renderPlan();
      case 'output':
        return renderOutput();
      case 'run':
      default:
        return renderRun();
    }
  };

  const tabs = SEGMENTS.filter((item) => !item.needsOutcome || resultReady);

  return (
    <Box
      data-testid="agent-cockpit"
      data-plan-id={plan?.id ?? ''}
      data-segment={view}
      sx={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, minHeight: 0 }}
    >
      {header ? (
        <Stack
          direction="row"
          alignItems="center"
          spacing={1}
          sx={{ px: 1.25, py: 0.5, borderBottom: 1, borderColor: 'divider' }}
        >
          <Box sx={{ flex: 1, minWidth: 0 }}>{header}</Box>
        </Stack>
      ) : null}

      {line ? (
        <Box sx={{ px: 1.25, py: 0.5, borderBottom: 1, borderColor: 'divider' }}>
          {line}
        </Box>
      ) : null}

      <Box sx={{ px: 1, py: 0.25, borderBottom: 1, borderColor: 'divider' }}>
        <ToggleButtonGroup
          value={view}
          exclusive
          size="small"
          onChange={(_e, next) => { if (next) onSegment?.(next); }}
          aria-label={t('cockpitView')}
          sx={{
            '& .MuiToggleButton-root': {
              border: 'none',
              px: 1.25,
              py: 0.25,
              fontSize: '0.75rem',
              textTransform: 'none',
              fontWeight: 500,
              color: 'text.secondary',
              '&.Mui-selected': {
                bgcolor: 'transparent',
                color: 'text.primary',
                fontWeight: 600,
                boxShadow: 'none',
                borderBottom: 2,
                borderColor: 'primary.main',
                borderRadius: 0,
              },
            },
          }}
        >
          {tabs.map(({ value, labelKey }) => (
            <ToggleButton
              key={value}
              value={value}
              aria-label={t(labelKey)}
            >
              {t(labelKey)}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {toolbar ? (
        <Box
          data-testid="agent-cockpit-toolbar"
          sx={{ px: 1.25, py: 0.5, borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}
        >
          {toolbar}
        </Box>
      ) : null}

      <Box
        sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1.25 }}
        data-testid="cockpit-body"
        data-hero={view}
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
  line: PropTypes.node,
  plan: PropTypes.object,
  renderPlan: PropTypes.func.isRequired,
  renderRun: PropTypes.func.isRequired,
  renderCanvas: PropTypes.func,
  renderOutput: PropTypes.func.isRequired,
  toolbar: PropTypes.node,
  resultReady: PropTypes.bool,
};

export default AgentCockpit;

/** Soft lifecycle default — Now while work is live, Picture to approve, Result after outcome. */
export function defaultCockpitSegment(effectiveStatus, phase) {
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
  if (hasTaskOutcome(effectiveStatus, phase)) {
    return 'output';
  }
  if (effectiveStatus === 'cancelled') return 'plan';
  return 'run';
}

/** Migrate ADR-0034 / Journey tab ids → Now · Picture · Result. */
export function normalizeCockpitSegment(raw) {
  if (raw === 'steps') return 'run';
  if (raw === 'metrics') return 'output';
  if (raw === 'canvas') return 'plan';
  if (raw === 'plan' || raw === 'run' || raw === 'output') return raw;
  return 'run';
}
