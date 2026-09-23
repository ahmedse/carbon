import React from 'react';
import { Box } from '@mui/material';
import { useTranslation } from 'react-i18next';

const WORKSPACE_ITEMS = [
  { id: 'chat', labelKey: 'modeChat', ariaKey: 'chatMode' },
  { id: 'tasks', labelKey: 'modeTasks', ariaKey: 'tasksMode' },
];

const THREAD_ITEMS = [
  { id: 'ask', labelKey: 'modeAsk', ariaKey: 'askMode' },
  { id: 'plan', labelKey: 'modePlan', ariaKey: 'planMode' },
];

function workspaceFromMode(mode) {
  return mode === 'agent' ? 'tasks' : 'chat';
}

function processFromMode(mode) {
  return mode === 'agent' ? 'plan' : 'ask';
}

/**
 * Trailing pills (header Chat/Tasks) or in-field pills (composer Ask/Plan).
 * Not a ToggleButtonGroup — that occupied a full row.
 */
export default function PulseProcessSwitch({
  variant = 'thread',
  value,
  onChange,
  disabled = false,
}) {
  const { t } = useTranslation('ai');
  const items = variant === 'workspace' ? WORKSPACE_ITEMS : THREAD_ITEMS;
  const testId = variant === 'workspace' ? 'pulse-workspace-switch' : 'pulse-process-switch';
  const compact = variant === 'thread';

  return (
    <Box
      role="group"
      data-testid={testId}
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.25,
        flexShrink: 0,
      }}
    >
      {items.map(({ id, labelKey, ariaKey }) => {
        const selected = value === id;
        return (
          <Box
            key={id}
            component="button"
            type="button"
            disabled={disabled}
            aria-label={t(ariaKey)}
            aria-pressed={selected}
            onClick={() => {
              if (!disabled && value !== id) onChange?.(id);
            }}
            sx={{
              appearance: 'none',
              border: 0,
              m: 0,
              px: 1,
              py: compact ? 0.375 : 0.25,
              borderRadius: 0.5,
              bgcolor: selected ? 'action.selected' : 'transparent',
              color: selected ? 'text.primary' : 'text.secondary',
              fontSize: compact ? '0.8125rem' : '0.75rem',
              fontWeight: selected ? 600 : 500,
              letterSpacing: '0.01em',
              lineHeight: 1.4,
              cursor: disabled ? 'default' : 'pointer',
              fontFamily: 'inherit',
              '&:hover': disabled
                ? undefined
                : { bgcolor: selected ? 'action.selected' : 'action.hover' },
              '&:disabled': { opacity: 0.5 },
            }}
          >
            {t(labelKey)}
          </Box>
        );
      })}
    </Box>
  );
}

export { workspaceFromMode, processFromMode };
