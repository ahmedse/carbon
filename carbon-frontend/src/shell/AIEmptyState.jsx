// src/shell/AIEmptyState.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, Typography } from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import SmartToyIcon from '@mui/icons-material/SmartToy';

const ILLUSTRATION_SIZE = 56;

function AIEmptyState({ onStartChat, manifests = [], onStartStarter }) {
  const hasDefaultStarters = manifests.some(
    (manifest) =>
      Array.isArray(manifest?.starter_prompts?.default) &&
      manifest.starter_prompts.default.length > 0,
  );

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        px: 3,
        textAlign: 'center',
        gap: 2,
        color: 'text.secondary',
      }}
    >
      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
        <SmartToyIcon
          sx={{ fontSize: ILLUSTRATION_SIZE, color: 'primary.light', opacity: 0.5 }}
        />
        <ChatIcon
          sx={{
            fontSize: 22,
            color: 'primary.main',
            position: 'absolute',
            bottom: -2,
            right: -6,
          }}
        />
      </Box>

      <Box>
        <Typography variant="subtitle2" color="text.primary" gutterBottom>
          AI Workspace Ready
        </Typography>
        <Typography variant="caption" color="text.disabled">
          Start a chat or transfer a task from the main workspace.
        </Typography>
      </Box>

      {hasDefaultStarters && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <Typography variant="caption" color="text.disabled">
            Start with a domain app
          </Typography>
          {manifests.map((manifest) => {
            const starters = manifest?.starter_prompts?.default;
            if (!Array.isArray(starters) || starters.length === 0) return null;
            return (
              <Box
                key={manifest.app_identifier}
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 1,
                }}
              >
                <Typography variant="overline" color="text.secondary">
                  {manifest.display_name}
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    justifyContent: 'center',
                    gap: 1,
                  }}
                >
                  {starters.map((item, index) => (
                    <Chip
                      key={`${manifest.app_identifier}:${index}`}
                      size="small"
                      variant="outlined"
                      clickable
                      label={item.label}
                      onClick={() =>
                        onStartStarter?.(
                          manifest.app_identifier,
                          item.task_type,
                          item.label,
                          item.prompt,
                        )
                      }
                    />
                  ))}
                </Box>
              </Box>
            );
          })}
        </Box>
      )}

      {onStartChat && (
        <Button
          variant="outlined"
          size="small"
          startIcon={<ChatIcon />}
          onClick={onStartChat}
        >
          Start a Chat
        </Button>
      )}
    </Box>
  );
}

AIEmptyState.propTypes = {
  onStartChat: PropTypes.func,
  manifests: PropTypes.array,
  onStartStarter: PropTypes.func,
};

export default AIEmptyState;
