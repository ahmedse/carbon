// src/shell/AgentCockpit.jsx
// U-1 (DESIGN-AGENT-WORKFLOW-AND-UI §6) — presentational run-cockpit shell that
// collapses the six-tab Agent panel into ONE contextual cockpit. It only
// arranges what it is given: a run header (title · status · global toolbar,
// built by the parent), a four-way segmented control (Plan · Steps · Output ·
// Metrics), and a Library overflow menu that demotes Templates/Scheduled from
// primary navigation. All state, handlers and API calls stay in AITaskPanel —
// this component is pure layout so it can be tested in isolation (RULE_2
// reuse; theme tokens only, RULE_8; outcome copy only, RULE_23).
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
import ViewListOutlinedIcon from '@mui/icons-material/ViewListOutlined';
import ArticleOutlinedIcon from '@mui/icons-material/ArticleOutlined';
import LeaderboardOutlinedIcon from '@mui/icons-material/LeaderboardOutlined';
import BookmarksOutlinedIcon from '@mui/icons-material/BookmarksOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import ViewColumnOutlinedIcon from '@mui/icons-material/ViewColumnOutlined';

const SEGMENTS = [
  { value: 'plan', label: 'Plan', icon: AccountTreeOutlinedIcon },
  { value: 'steps', label: 'Steps', icon: ViewListOutlinedIcon },
  { value: 'output', label: 'Output', icon: ArticleOutlinedIcon },
  { value: 'metrics', label: 'Metrics', icon: LeaderboardOutlinedIcon },
];

/**
 * Run-cockpit layout shell.
 * @param {object} props
 * @param {'plan'|'steps'|'output'|'metrics'} props.segment - active segment
 * @param {function} props.onSegment - (value) => void
 * @param {React.ReactNode} props.header - run header (title · status · toolbar)
 * @param {object|null} props.plan - selected plan (for context only)
 * @param {function} props.renderPlan - () => node for the Plan segment
 * @param {function} props.renderSteps - () => node for the Steps segment
 * @param {function} props.renderOutput - () => node for the Output segment
 * @param {function} props.renderMetrics - () => node for the Metrics segment
 * @param {function} [props.onOpenTemplates] - Library → Templates
 * @param {function} [props.onOpenScheduled] - Library → Scheduled
 * @param {function} [props.onSwitchToClassic] - Library → classic 6-tab view
 */
function AgentCockpit({
  segment,
  onSegment,
  header,
  plan,
  renderPlan,
  renderSteps,
  renderOutput,
  renderMetrics,
  onOpenTemplates,
  onOpenScheduled,
  onSwitchToClassic,
}) {
  const [libraryAnchor, setLibraryAnchor] = useState(null);
  const libraryOpen = Boolean(libraryAnchor);
  const closeLibrary = () => setLibraryAnchor(null);

  const body = () => {
    switch (segment) {
      case 'plan':
        return renderPlan();
      case 'output':
        return renderOutput();
      case 'metrics':
        return renderMetrics();
      case 'steps':
      default:
        return renderSteps();
    }
  };

  return (
    <Box
      data-testid="agent-cockpit"
      data-plan-id={plan?.id ?? ''}
      sx={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, minHeight: 0 }}
    >
      {/* Cockpit header — run title/status/toolbar (parent) + Library overflow */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 1, py: 0.5, borderBottom: 1, borderColor: 'divider' }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>{header}</Box>
        <Tooltip title="Library">
          <IconButton
            size="small"
            aria-label="Library"
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
            <ListItemText primaryTypographyProps={{ fontSize: '0.75rem' }}>Templates</ListItemText>
          </MenuItem>
          <MenuItem onClick={() => { closeLibrary(); onOpenScheduled?.(); }}>
            <ListItemIcon><ScheduleOutlinedIcon sx={{ fontSize: 16 }} /></ListItemIcon>
            <ListItemText primaryTypographyProps={{ fontSize: '0.75rem' }}>Scheduled</ListItemText>
          </MenuItem>
          <Divider />
          <MenuItem onClick={() => { closeLibrary(); onSwitchToClassic?.(); }}>
            <ListItemIcon><ViewColumnOutlinedIcon sx={{ fontSize: 16 }} /></ListItemIcon>
            <ListItemText primaryTypographyProps={{ fontSize: '0.75rem' }}>Switch to classic view</ListItemText>
          </MenuItem>
        </Menu>
      </Stack>

      {/* Segmented control — Plan · Steps · Output · Metrics */}
      <Box sx={{ px: 1, py: 0.5, borderBottom: 1, borderColor: 'divider' }}>
        <ToggleButtonGroup
          value={segment}
          exclusive
          size="small"
          fullWidth
          onChange={(_e, next) => { if (next) onSegment?.(next); }}
          aria-label="Run cockpit view"
        >
          {SEGMENTS.map(({ value, label, icon: Icon }) => (
            <ToggleButton
              key={value}
              value={value}
              aria-label={label}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', py: 0.25, gap: 0.5 }}
            >
              <Icon sx={{ fontSize: 14 }} />
              {label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {/* Segment body */}
      <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }} data-testid="cockpit-body">
        {body()}
      </Box>
    </Box>
  );
}

AgentCockpit.propTypes = {
  segment: PropTypes.oneOf(['plan', 'steps', 'output', 'metrics']).isRequired,
  onSegment: PropTypes.func.isRequired,
  header: PropTypes.node,
  plan: PropTypes.object,
  renderPlan: PropTypes.func.isRequired,
  renderSteps: PropTypes.func.isRequired,
  renderOutput: PropTypes.func.isRequired,
  renderMetrics: PropTypes.func.isRequired,
  onOpenTemplates: PropTypes.func,
  onOpenScheduled: PropTypes.func,
  onSwitchToClassic: PropTypes.func,
};

export default AgentCockpit;
