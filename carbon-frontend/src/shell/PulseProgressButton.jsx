// src/shell/PulseProgressButton.jsx
// Discoverable Pulse-shell affordance that opens the read-only progress canvas
// (excellence ladder + intention recognition). Same primitive shape as
// OpsCanvasAttachButton: a small outlined Button + Tooltip that opens a Dialog.
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import CloseIcon from '@mui/icons-material/Close';
import { useTranslation } from 'react-i18next';
import PulseProgressCanvas from './PulseProgressCanvas';

/**
 * @param {object} props
 * @param {boolean} [props.canView] — same gate as the canvas surface (authenticated);
 *   the header passes `Boolean(token)`.
 */
export default function PulseProgressButton({ canView = true }) {
  const { t } = useTranslation('ai');
  const [open, setOpen] = useState(false);

  if (!canView) return null;

  return (
    <>
      <Tooltip title={t('progress.buttonHint')}>
        <Button
          size="small"
          variant="outlined"
          startIcon={<InsightsOutlinedIcon sx={{ fontSize: 16 }} />}
          onClick={() => setOpen(true)}
          data-testid="pulse-progress-button"
          sx={{ ml: 0.5, px: 1, py: 0.25, minWidth: 0, textTransform: 'none', fontSize: '0.6875rem' }}
        >
          {t('progress.button')}
        </Button>
      </Tooltip>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="md"
        PaperProps={{ sx: { height: '80vh' } }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', pr: 1 }}>
          <Typography variant="subtitle1" fontWeight={700} sx={{ flex: 1 }}>
            {t('progress.title')}
          </Typography>
          <IconButton onClick={() => setOpen(false)} aria-label={t('progress.close')} size="small">
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 0 }}>
          <PulseProgressCanvas />
        </DialogContent>
      </Dialog>
    </>
  );
}

PulseProgressButton.propTypes = {
  canView: PropTypes.bool,
};
