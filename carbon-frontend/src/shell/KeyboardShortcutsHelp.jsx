// File: src/shell/KeyboardShortcutsHelp.jsx
// Help dialog showing all keyboard shortcuts

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  Divider,
  IconButton,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardIcon from '@mui/icons-material/Keyboard';

const SHORTCUTS = [
  {
    category: 'Navigation',
    items: [
      { keys: ['Ctrl', 'K'], description: 'Open Command Palette' },
      { keys: ['Ctrl', 'B'], description: 'Toggle Sidebar' },
      { keys: ['Ctrl', '\\'], description: 'Toggle Pulse' },
      { keys: ['Esc'], description: 'Close dialogs/modals' },
    ],
  },
  {
    category: 'Theme & Display',
    items: [
      { keys: ['Ctrl', 'Shift', 'T'], description: 'Toggle Theme (Light/Dark)' },
    ],
  },
  {
    category: 'Command Palette',
    items: [
      { keys: ['↑', '↓'], description: 'Navigate through commands' },
      { keys: ['Enter'], description: 'Execute selected command' },
      { keys: ['Esc'], description: 'Close Command Palette' },
    ],
  },
  {
    category: 'Studio Navigation',
    items: [
      { keys: ['Alt', '1'], description: 'Go to Dashboard' },
      { keys: ['Alt', '2'], description: 'Go to Emissions' },
      { keys: ['Alt', '3'], description: 'Go to Carbon Data Entry' },
      { keys: ['Alt', '4'], description: 'Go to Admin' },
      { keys: ['Alt', '5'], description: 'Go to Settings' },
      { keys: ['Alt', '6'], description: 'Go to Help' },
    ],
  },
];

function KeyBadge({ keyLabel }) {
  return (
    <Box
      component="kbd"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 28,
        height: 24,
        px: 1,
        bgcolor: 'background.paper',
        border: 1,
        borderColor: 'divider',
        borderRadius: 0.5,
        fontSize: '0.75rem',
        fontWeight: 600,
        fontFamily: 'monospace',
        color: 'text.primary',
        boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
      }}
    >
      {keyLabel}
    </Box>
  );
}

export function KeyboardShortcutsHelp({ open, onClose }) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="shortcuts-dialog-title"
      PaperProps={{
        sx: {
          borderRadius: 2,
        },
      }}
    >
      <DialogTitle
        id="shortcuts-dialog-title"
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          pb: 1,
        }}
      >
        <KeyboardIcon sx={{ color: 'primary.main' }} aria-hidden="true" />
        <Typography variant="h6" component="h2" sx={{ flex: 1, fontWeight: 600 }}>
          Keyboard Shortcuts
        </Typography>
        <IconButton size="small" onClick={onClose} aria-label="Close shortcuts dialog">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ py: 3 }}>
        {SHORTCUTS.map((section, sectionIndex) => (
          <Box key={section.category} sx={{ mb: sectionIndex < SHORTCUTS.length - 1 ? 3 : 0 }}>
            <Typography
              variant="overline"
              sx={{
                display: 'block',
                fontWeight: 700,
                color: 'text.secondary',
                mb: 1.5,
                letterSpacing: 1,
              }}
            >
              {section.category}
            </Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {section.items.map((item, itemIndex) => (
                <Box
                  key={itemIndex}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 2,
                  }}
                >
                  <Typography
                    sx={{
                      fontSize: '0.875rem',
                      color: 'text.primary',
                      flex: 1,
                    }}
                  >
                    {item.description}
                  </Typography>

                  <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                    {item.keys.map((key, keyIndex) => (
                      <React.Fragment key={keyIndex}>
                        <KeyBadge keyLabel={key} />
                        {keyIndex < item.keys.length - 1 && (
                          <Typography
                            sx={{
                              fontSize: '0.75rem',
                              color: 'text.disabled',
                              mx: 0.25,
                            }}
                          >
                            +
                          </Typography>
                        )}
                      </React.Fragment>
                    ))}
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>
        ))}

        <Box
          sx={{
            mt: 4,
            p: 2,
            bgcolor: 'action.hover',
            borderRadius: 1,
            border: 1,
            borderColor: 'divider',
          }}
        >
          <Typography
            sx={{
              fontSize: '0.75rem',
              color: 'text.secondary',
              fontStyle: 'italic',
            }}
          >
            <strong>Note:</strong> On Mac, use <KeyBadge keyLabel="⌘" /> (Command) instead of{' '}
            <KeyBadge keyLabel="Ctrl" />
          </Typography>
        </Box>
      </DialogContent>
    </Dialog>
  );
}
