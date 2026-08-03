// File: src/components/panel/PanelConfigDialog.jsx
// Gear-icon dialog to show/hide specific right-panel tabs.
// Persists config as JSON in localStorage.

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Typography,
} from '@mui/material';

export default function PanelConfigDialog({ open, onClose, tabs, config, onSave }) {
  const [draft, setDraft] = useState({ ...config });

  if (!open) return null;

  const handleToggle = (label) => {
    setDraft((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  const handleSave = () => {
    onSave(draft);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontSize: '0.9rem', fontWeight: 700, pb: 1 }}>
        Configure Panel Tabs
      </DialogTitle>
      <DialogContent sx={{ pt: 1 }}>
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.72rem', mb: 1.5 }}>
          Show or hide tabs in the right panel. Hidden tabs are ignored when cycling through.
        </Typography>
        <FormGroup>
          {tabs.map((tab) => (
            <FormControlLabel
              key={tab.label}
              control={
                <Checkbox
                  size="small"
                  checked={draft[tab.label] !== false}
                  onChange={() => handleToggle(tab.label)}
                />
              }
              label={
                <Typography sx={{ fontSize: '0.78rem' }}>
                  {tab.label}
                </Typography>
              }
              sx={{ '.MuiFormControlLabel-label': { fontSize: '0.78rem' } }}
            />
          ))}
        </FormGroup>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} size="small" sx={{ fontSize: '0.72rem' }}>
          Cancel
        </Button>
        <Button onClick={handleSave} size="small" variant="contained" sx={{ fontSize: '0.72rem' }}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
