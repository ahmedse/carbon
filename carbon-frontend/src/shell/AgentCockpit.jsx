// src/shell/AgentCockpit.jsx
// ADR-0043 — presentational run-cockpit shell: Plan · Run · Canvas · Output
// (exclusive heroes). Parent owns state/handlers; this is pure layout (RULE_2).
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Divider,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
} from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import MapOutlinedIcon from '@mui/icons-material/MapOutlined';
import ArticleOutlinedIcon from '@mui/icons-material/ArticleOutlined';
import BookmarksOutlinedIcon from '@mui/icons-material/BookmarksOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import ViewColumnOutlinedIcon from '@mui/icons-material/ViewColumnOutlined';
import { useTranslation } from 'react-i18next';

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
 * @param {function} [props.onOpenTemplates]
 * @param {function} [props.onOpenScheduled]
 * @param {function} [props.onSwitchToClassic]
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
  onOpenTemplates,
  onOpenScheduled,
  onSwitchToClassic,
}) {
  const { t } = useTranslation('ai');
  const [libraryAnchor, setLibraryAnchor] = useState(null);
  const libraryOpen = Boolean(libraryAnchor);
  const closeLibrary = () => setLibraryAnchor(null);

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
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 1, py: 0.5, borderBottom: 1, borderColor: 'divider' }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>{header}</Box>
        <Tooltip title={t('library')}>
          <IconButton
            size="small"
            aria-label={t('library')}
            aria-haspopup="menu"
            onClick={(e) => setLibraryAnchor(e.currentTarget)}
            sx={{ p: 0.375 }}
          >
            <MoreVertIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
        <Menu anchorEl={libraryAnchor} open={libraryOpen} onClose={closeLibrary}>
          <MenuItem onClick={() => { closeLibrary(); onOpenTemplates?.(); }}>
            <ListItemIcon><BookmarksOutlinedIcon sx={{ fontSize: 16 }} /></ListItemIcon>
            <ListItemText primaryTypographyProps={{ fontSize: '0.75rem' }}>{t('templates')}</ListItemText>
          </MenuItem>
          <MenuItem onClick={() => { closeLibrary(); onOpenScheduled?.(); }}>
            <ListItemIcon><ScheduleOutlinedIcon sx={{ fontSize: 16 }} /></ListItemIcon>
            <ListItemText primaryTypographyProps={{ fontSize: '0.75rem' }}>{t('scheduled')}</ListItemText>
          </MenuItem>
          <Divider />
          <MenuItem onClick={() => { closeLibrary(); onSwitchToClassic?.(); }}>
            <ListItemIcon><ViewColumnOutlinedIcon sx={{ fontSize: 16 }} /></ListItemIcon>
            <ListItemText primaryTypographyProps={{ fontSize: '0.75rem' }}>{t('switchClassic')}</ListItemText>
          </MenuItem>
        </Menu>
      </Stack>

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

      <Box
        sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}
        data-testid="cockpit-body"
        data-hero={segment}
      >
        <Box data-testid={heroTestId}>
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
  onOpenTemplates: PropTypes.func,
  onOpenScheduled: PropTypes.func,
  onSwitchToClassic: PropTypes.func,
};

export default AgentCockpit;

/** Soft lifecycle default (ADR-0043 §2). */
export function defaultCockpitSegment(effectiveStatus, phase) {
  // Settled session phases win so Output can show stop/fail chrome.
  if (phase === 'stopped' || phase === 'error' || phase === 'finished') {
    return 'output';
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
