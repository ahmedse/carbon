// src/shell/AIArtifactCard.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, IconButton, Paper, Stack, Tooltip, Typography } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import AssessmentIcon from '@mui/icons-material/Assessment';
import QueryStatsIcon from '@mui/icons-material/QueryStats';
import RuleIcon from '@mui/icons-material/Rule';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ArticleIcon from '@mui/icons-material/Article';
import { formatDistanceToNow } from '../utils/dateUtils';

const TYPE_META = {
  report:    { label: 'Report',    icon: AssessmentIcon,  color: 'primary' },
  query:     { label: 'Query',     icon: QueryStatsIcon,  color: 'info' },
  rule_set:  { label: 'Rule set',  icon: RuleIcon,        color: 'warning' },
  analysis:  { label: 'Analysis',  icon: AnalyticsIcon,   color: 'secondary' },
};

function typeIcon(artifactType) {
  const cfg = TYPE_META[artifactType];
  if (!cfg) return ArticleIcon;
  return cfg.icon;
}

function AIArtifactCard({ artifact, onOpen }) {
  const cfg = TYPE_META[artifact.artifact_type] || { label: artifact.artifact_type || 'Artifact', color: 'default' };
  const Icon = typeIcon(artifact.artifact_type);
  const createdAt = artifact.created_at ? new Date(artifact.created_at) : null;

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1.25,
        transition: 'border-color 0.1s',
        '&:hover': { borderColor: 'primary.main' },
      }}
    >
      <Box sx={{ mt: 0.25, color: `${cfg.color}.main`, flexShrink: 0 }}>
        <Icon fontSize="small" />
      </Box>

      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          fontWeight={600}
          noWrap
          title={artifact.title}
        >
          {artifact.title || 'Untitled artifact'}
        </Typography>

        <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mt: 0.5 }}>
          <Chip size="small" color={cfg.color} label={cfg.label} sx={{ height: 16, '& .MuiChip-label': { px: 0.75, fontSize: '0.6rem' } }} />
          {createdAt && (
            <Typography variant="caption" color="text.disabled">
              {formatDistanceToNow(createdAt)}
            </Typography>
          )}
        </Stack>
      </Box>

      <Tooltip title="Open artifact">
        <IconButton
          size="small"
          onClick={() => onOpen?.(artifact)}
          aria-label={`Open artifact ${artifact.title}`}
          sx={{ flexShrink: 0, mt: -0.25 }}
        >
          <OpenInNewIcon sx={{ fontSize: 14 }} />
        </IconButton>
      </Tooltip>
    </Paper>
  );
}

AIArtifactCard.propTypes = {
  artifact: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    title: PropTypes.string,
    artifact_type: PropTypes.string,
    created_at: PropTypes.string,
    content_json: PropTypes.object,
  }).isRequired,
  onOpen: PropTypes.func,
};

export default AIArtifactCard;
