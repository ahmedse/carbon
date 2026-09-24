/**
 * Collapsible + resizable Run step detail drawer — same height as the
 * timeline/graph dock. Opens when a beat is selected.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import StepActionBar from './StepActionBar';

const WIDTH_KEY = 'pulse.runStepDetail.width';
const MIN_W = 240;
const MAX_W = 480;
const DEFAULT_W = 320;

function readStoredWidth() {
  try {
    const n = Number(localStorage.getItem(WIDTH_KEY));
    if (Number.isFinite(n) && n >= MIN_W && n <= MAX_W) return n;
  } catch {
    /* ignore */
  }
  return DEFAULT_W;
}

export default function RunStepDetailDrawer({
  open,
  step,
  event = null,
  confirming = false,
  onConfirm = null,
  onDecline = null,
  onClose = null,
  busy = false,
  stepActions = null,
}) {
  const needsConsent = step?.status === 'awaiting_approval';
  const [width, setWidth] = useState(readStoredWidth);
  const drag = useRef(null);

  useEffect(() => {
    try {
      localStorage.setItem(WIDTH_KEY, String(width));
    } catch {
      /* ignore */
    }
  }, [width]);

  const onResizeMove = useCallback((e) => {
    const g = drag.current;
    if (!g) return;
    const next = Math.min(MAX_W, Math.max(MIN_W, g.startW + (g.startX - e.clientX)));
    setWidth(next);
  }, []);

  const onResizeEnd = useCallback(() => {
    drag.current = null;
    window.removeEventListener('mousemove', onResizeMove);
    window.removeEventListener('mouseup', onResizeEnd);
  }, [onResizeMove]);

  const onResizeStart = (e) => {
    e.preventDefault();
    e.stopPropagation();
    drag.current = { startX: e.clientX, startW: width };
    window.addEventListener('mousemove', onResizeMove);
    window.addEventListener('mouseup', onResizeEnd);
  };

  useEffect(() => () => {
    window.removeEventListener('mousemove', onResizeMove);
    window.removeEventListener('mouseup', onResizeEnd);
  }, [onResizeMove, onResizeEnd]);

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
          width: { xs: Math.min(width, 280), sm: width },
          height: '100%',
          minHeight: 0,
          alignSelf: 'stretch',
          borderLeft: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
          display: 'flex',
          flexDirection: 'row',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <Box
          data-testid="run-step-detail-resize"
          onMouseDown={onResizeStart}
          sx={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: 6,
            cursor: 'col-resize',
            zIndex: 2,
            '&:hover': { bgcolor: 'action.hover' },
          }}
          aria-hidden
        />
        <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
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
            {!needsConsent && stepActions && (
              <StepActionBar step={step} busy={busy || confirming} {...stepActions} />
            )}
          </Box>
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
  busy: PropTypes.bool,
  /** { onRetry, onSkip, onPause, onResume, onCancel, onEditInPlan, onDiscussInPlan } */
  stepActions: PropTypes.object,
};
