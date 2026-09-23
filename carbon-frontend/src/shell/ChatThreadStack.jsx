// In-session thread stack — Copilot-style topics inside one conversation.
// RULE_8 theme tokens only. Not the sessions accordion (that lives left in AIWorkspace).
import React from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import { turnCount } from './chatThreads';

function threadLabel(thread, t) {
  if (thread.title) return thread.title;
  if (thread.titleKey) return t(thread.titleKey);
  return t('mainThread');
}

export default function ChatThreadStack({
  state,
  onSelect,
  onNew,
  compact = false,
}) {
  const { t } = useTranslation('ai');
  if (!state?.threads?.length) return null;

  // Hide the strip when only Main exists and it has no sibling topics yet.
  const onlyMain = state.threads.length === 1;
  if (onlyMain && compact) {
    // Still show a slim bar so users can start a topic (+).
  }

  return (
    <Box
      data-testid="chat-thread-stack"
      sx={{
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        px: 1,
        py: 0.5,
        flexShrink: 0,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          mb: compact ? 0 : 0.25,
        }}
      >
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ fontSize: '0.625rem', letterSpacing: '0.04em', flexShrink: 0 }}
        >
          {t('activeThread')}
        </Typography>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'row',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 0.5,
            flex: 1,
            minWidth: 0,
            ...(compact
              ? {}
              : {
                  flexDirection: 'column',
                  alignItems: 'stretch',
                  maxHeight: 140,
                  overflowY: 'auto',
                }),
          }}
        >
          {state.threads.map((thread) => {
            const active = thread.id === state.activeId;
            const count = turnCount(state, thread.id);
            const label = threadLabel(thread, t);
            return (
              <Box
                key={thread.id}
                component="button"
                type="button"
                data-testid={`chat-thread-${thread.id}`}
                aria-pressed={active}
                onClick={() => onSelect(thread.id)}
                sx={{
                  appearance: 'none',
                  border: 1,
                  borderColor: active ? 'primary.main' : 'divider',
                  m: 0,
                  textAlign: 'start',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  px: 0.75,
                  py: 0.35,
                  borderRadius: 0,
                  bgcolor: active ? 'action.selected' : 'transparent',
                  color: 'text.primary',
                  maxWidth: compact ? 180 : '100%',
                  '&:hover': { bgcolor: active ? 'action.selected' : 'action.hover' },
                }}
              >
                <Typography
                  component="span"
                  sx={{
                    display: 'block',
                    fontSize: '0.6875rem',
                    fontWeight: active ? 600 : 500,
                    lineHeight: 1.3,
                    unicodeBidi: 'plaintext',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {label}
                  {count > 0 ? (
                    <Typography
                      component="span"
                      color="text.secondary"
                      sx={{ fontSize: '0.625rem', ml: 0.5, fontWeight: 400 }}
                    >
                      · {count}
                    </Typography>
                  ) : null}
                </Typography>
              </Box>
            );
          })}
        </Box>
        <Tooltip title={t('newThread')}>
          <IconButton
            size="small"
            onClick={onNew}
            aria-label={t('newThread')}
            data-testid="chat-thread-new"
            sx={{ p: 0.25, flexShrink: 0 }}
          >
            <AddIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

ChatThreadStack.propTypes = {
  state: PropTypes.shape({
    activeId: PropTypes.string,
    threads: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string.isRequired,
        title: PropTypes.string,
        titleKey: PropTypes.string,
      }),
    ),
    membership: PropTypes.object,
  }),
  onSelect: PropTypes.func.isRequired,
  onNew: PropTypes.func.isRequired,
  compact: PropTypes.bool,
};
