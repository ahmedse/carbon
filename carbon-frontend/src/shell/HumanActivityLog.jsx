// Optional accordion — plain-language activity log under Plan graph / Now timeline.
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Collapse,
  IconButton,
  Stack,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useTranslation } from 'react-i18next';

const TONE_COLOR = {
  success: 'success.main',
  error: 'error.main',
  warning: 'warning.main',
  primary: 'primary.main',
  default: 'text.disabled',
};

/**
 * @param {object} props
 * @param {Array<{ id: string, tone: string, line: string }>} props.lines
 * @param {boolean} [props.defaultOpen]
 */
export default function HumanActivityLog({ lines = [], defaultOpen = false }) {
  const { t } = useTranslation('ai');
  const [open, setOpen] = useState(defaultOpen);
  const list = Array.isArray(lines) ? lines : [];
  if (!list.length) return null;

  return (
    <Box
      data-testid="human-activity-log"
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        bgcolor: 'background.paper',
        overflow: 'hidden',
      }}
    >
      <Stack
        direction="row"
        alignItems="center"
        spacing={0.5}
        onClick={() => setOpen((v) => !v)}
        sx={{
          px: 1,
          py: 0.625,
          cursor: 'pointer',
          '&:hover': { bgcolor: 'action.hover' },
          userSelect: 'none',
        }}
        role="button"
        aria-expanded={open}
        aria-controls="human-activity-log-panel"
      >
        <IconButton
          size="small"
          aria-label={open ? t('activityLogHide') : t('activityLogShow')}
          sx={{ p: 0 }}
        >
          {open
            ? <ExpandMoreIcon sx={{ fontSize: '1rem' }} />
            : <ChevronRightIcon sx={{ fontSize: '1rem' }} />}
        </IconButton>
        <Typography
          variant="caption"
          sx={{
            flex: 1,
            fontWeight: 700,
            fontSize: '0.6875rem',
            letterSpacing: '0.02em',
            color: 'text.secondary',
          }}
        >
          {t('activityLogTitle')}
        </Typography>
        <Typography variant="caption" color="text.disabled" sx={{ fontSize: '0.625rem' }}>
          {list.length}
        </Typography>
      </Stack>
      <Collapse in={open} timeout={120}>
        <Stack
          id="human-activity-log-panel"
          spacing={0.5}
          sx={{ px: 1.25, pb: 1, pt: 0.25 }}
          data-testid="human-activity-log-panel"
        >
          {list.map((row) => (
            <Stack key={row.id} direction="row" spacing={0.75} alignItems="flex-start">
              <Box
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  bgcolor: TONE_COLOR[row.tone] || TONE_COLOR.default,
                  mt: '0.35rem',
                  flexShrink: 0,
                }}
              />
              <Typography
                variant="body2"
                sx={{ fontSize: '0.75rem', lineHeight: 1.4, color: 'text.primary' }}
              >
                {row.line}
              </Typography>
            </Stack>
          ))}
        </Stack>
      </Collapse>
    </Box>
  );
}

HumanActivityLog.propTypes = {
  lines: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    tone: PropTypes.string,
    line: PropTypes.string.isRequired,
  })),
  defaultOpen: PropTypes.bool,
};
