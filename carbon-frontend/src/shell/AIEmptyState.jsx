// Empty Ask — a coworker introduction, not a domain-app catalog.
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import PulseLogo from './PulseLogo';

function AIEmptyState({ onStartChat, onStartStarter, intro, suggestions: suggestionOverride }) {
  const { t } = useTranslation('ai');
  // Domain manifests are every registered app, not this user's. Their first
  // chips (budget variance, attrition) are another brand's catalog, and the
  // prompt still contains @{entity_name}. These two questions work for whoever
  // is signed in.
  const suggestions = suggestionOverride || [
    {
      appId: '',
      taskType: 'chat',
      label: t('emptyTryCapabilities'),
      prompt: t('emptyTryCapabilitiesPrompt'),
    },
    {
      appId: '',
      taskType: 'chat',
      label: t('emptyTryCatchUp'),
      prompt: t('emptyTryCatchUpPrompt'),
    },
  ];

  return (
    <Box
      data-testid="pulse-empty-state"
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        px: 3,
        py: 4,
        color: 'text.secondary',
      }}
    >
      <Stack
        spacing={2}
        sx={{
          width: '100%',
          maxWidth: '36rem',
          alignItems: 'flex-start',
          textAlign: 'start',
        }}
      >
        <PulseLogo size={36} />

        <Box>
          <Typography
            variant="h6"
            color="text.primary"
            sx={{ fontWeight: 600, letterSpacing: '-0.02em', mb: 0.75 }}
          >
            {t('emptyHello')}
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ fontSize: '0.875rem', lineHeight: 1.55, maxWidth: '40ch' }}
          >
            {intro || t('emptyIntro')}
          </Typography>
        </Box>

        {onStartChat ? (
          <Button
            variant="contained"
            size="small"
            onClick={onStartChat}
            sx={{ textTransform: 'none', fontWeight: 600 }}
          >
            {t('emptyStart')}
          </Button>
        ) : null}

        <Box>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: 0.75, fontWeight: 600, letterSpacing: '0.02em' }}
          >
            {t('emptyTry')}
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
            {suggestions.map((item) => (
              <Chip
                key={`${item.appId}:${item.label}`}
                size="small"
                variant="outlined"
                clickable
                label={item.label}
                onClick={() =>
                  onStartStarter?.(item.appId, item.taskType, item.label, item.prompt)
                }
              />
            ))}
          </Box>
        </Box>
      </Stack>
    </Box>
  );
}

AIEmptyState.propTypes = {
  onStartChat: PropTypes.func,
  onStartStarter: PropTypes.func,
  intro: PropTypes.string,
  suggestions: PropTypes.arrayOf(PropTypes.shape({
    appId: PropTypes.string,
    taskType: PropTypes.string,
    label: PropTypes.string,
    prompt: PropTypes.string,
  })),
};

export default AIEmptyState;
