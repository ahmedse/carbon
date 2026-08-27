// src/notes/ReactionBar.jsx
// Tiny reaction buttons (👍 ❓ ⭐) with counts, single-tap toggle, optimistic.
// Used on both notes and comments.

import React from 'react';
import { Box, Tooltip, ButtonBase } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { REACTION_CHOICES } from './notesUtils';

/**
 * @param {object} props
 * @param {object} props.reaction_counts  { like, question, star }
 * @param {string|null} props.my_reaction
 * @param {function(string): void} props.onToggle
 * @param {boolean} [props.disabled]
 * @param {'small'|'medium'} [props.size]
 */
export function ReactionBar({ reaction_counts = {}, my_reaction = null, onToggle, disabled = false, size = 'small' }) {
  const { t } = useTranslation('notes');

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.25,
        flexWrap: 'wrap',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {REACTION_CHOICES.map((choice) => {
        const count = reaction_counts?.[choice.value] ?? 0;
        const active = my_reaction === choice.value;
        return (
          <Tooltip key={choice.value} title={t(choice.labelKey)}>
            <ButtonBase
              disabled={disabled}
              onClick={() => onToggle?.(choice.value)}
              aria-pressed={active}
              aria-label={`${choice.icon} ${count}`}
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.2,
                px: 0.35,
                py: 0.1,
                borderRadius: 1,
                fontSize: size === 'small' ? '0.6rem' : '0.7rem',
                lineHeight: 1.2,
                color: active ? 'primary.main' : 'text.secondary',
                bgcolor: active ? 'primary.soft' : 'transparent',
                '&:hover': { bgcolor: 'action.hover' },
                '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' },
                userSelect: 'none',
              }}
            >
              <span aria-hidden="true" style={{ fontSize: '0.72em' }}>{choice.icon}</span>
              <span style={{ minWidth: 9, textAlign: 'center' }}>{count}</span>
            </ButtonBase>
          </Tooltip>
        );
      })}
    </Box>
  );
}
