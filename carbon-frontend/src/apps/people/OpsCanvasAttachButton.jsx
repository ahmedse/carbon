/** Open Ops Canvas Job Maps attached to a domain record (ADR-0041 Phase 4). */
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Button, Dialog, DialogContent, DialogTitle, IconButton, Tooltip } from '@mui/material';
import MapOutlinedIcon from '@mui/icons-material/MapOutlined';
import CloseIcon from '@mui/icons-material/Close';
import OpsCanvasShelf from '../../shell/OpsCanvasShelf';

export default function OpsCanvasAttachButton({
  relatedType,
  relatedId,
  relatedLabel = '',
  conversationId = null,
}) {
  const [open, setOpen] = useState(false);
  if (!relatedType || relatedId == null || relatedId === '') return null;

  return (
    <>
      <Tooltip title="Ops Canvas — what this task/job requires">
        <Button
          size="small"
          variant="outlined"
          startIcon={<MapOutlinedIcon />}
          onClick={() => setOpen(true)}
          data-testid="ops-canvas-attach"
          sx={{ textTransform: 'none' }}
        >
          Job Map
        </Button>
      </Tooltip>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="md" PaperProps={{ sx: { height: '80vh' } }}>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center' }}>
          Job Map — {relatedLabel || `${relatedType} #${relatedId}`}
          <IconButton onClick={() => setOpen(false)} sx={{ ml: 'auto' }} aria-label="Close">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 0 }}>
          <OpsCanvasShelf
            conversationId={conversationId}
            relatedType={relatedType}
            relatedId={String(relatedId)}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}

OpsCanvasAttachButton.propTypes = {
  relatedType: PropTypes.string.isRequired,
  relatedId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  relatedLabel: PropTypes.string,
  conversationId: PropTypes.string,
};
