/**
 * Collapsible Run step detail drawer — opens when a timeline beat is selected.
 * Holds consent form + Approve/Decline (no inline expansion on the timeline).
 */
import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Collapse,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import BeatDetailContent from './BeatDetailContent';
import TimelineConsentForm from './TimelineConsentForm';

export default function RunStepDetailDrawer({
  open,
  step,
  event = null,
  confirming = false,
  onConfirm = null,
  onDecline = null,
  onClose = null,
}) {
  const needsConsent = step?.status === 'awaiting_approval';

  return (
    <Collapse
      in={open && Boolean(step)}
      orientation="horizontal"
      unmountOnExit
      timeout={120}
      sx={{ height: '100%', alignSelf: 'stretch' }}
    >
      <Box
        data-testid="run-step-detail-drawer"
        sx={{
          width: { xs: 280, sm: 320 },
          height: '100%',
          minHeight: 280,
          borderLeft: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <Stack
          direction="row"
          alignItems="center"
          spacing={0.5}
          sx={{
            px: 1.25,
            py: 0.75,
            borderBottom: 1,
            borderColor: 'divider',
            flexShrink: 0,
          }}
        >
          <Typography
            variant="caption"
            sx={{
              flex: 1,
              fontWeight: 700,
              fontSize: '0.625rem',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'text.secondary',
            }}
          >
            Step details
          </Typography>
          <Tooltip title="Close">
            <IconButton
              size="small"
              aria-label="Close step details"
              data-testid="run-step-detail-close"
              onClick={onClose}
              sx={{ p: 0.25 }}
            >
              <CloseIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Stack>

        <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1.25 }}>
          <BeatDetailContent step={step} event={event} busy={confirming} hideConsentHint />
          {needsConsent && (onConfirm || onDecline) && (
            <Box sx={{ mt: 1.5 }} data-testid="run-step-detail-consent">
              <TimelineConsentForm
                step={step}
                confirming={confirming}
                onConfirm={onConfirm}
                onDecline={onDecline}
              />
            </Box>
          )}
        </Box>
      </Box>
    </Collapse>
  );
}

RunStepDetailDrawer.propTypes = {
  open: PropTypes.bool,
  step: PropTypes.object,
  event: PropTypes.object,
  confirming: PropTypes.bool,
  onConfirm: PropTypes.func,
  onDecline: PropTypes.func,
  onClose: PropTypes.func,
};
