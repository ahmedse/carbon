// src/shell/AIWorkspaceHeader.jsx
// W5-A (ADR-0014) — Chat and Agent are the two top-level Pulse modes. Mode
// lives HERE (workspace level), not in the composer. The always-visible
// safety-contract text sits beside the mode buttons and changes with the
// agent lifecycle so the trust contract is legible at all times.
// RULE_8: theme tokens only (no hex/raw px). RULE_3: compact density.

import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import {
  Box,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import PulseLogo from './PulseLogo';
import AIContextMenu from './AIContextMenu';

// ADR-0014 §4 — the safety contract is always visible in the header. Exact
// copy per the decision table; the header must never invent new wording.
// Keys resolve to the `ai.contract.*` namespace (I18N-5).
const CONTRACT_TEXT_KEYS = {
  chat: 'contract.chat',
  idle: 'contract.idle',
  plan_pending: 'contract.planPending',
  running: 'contract.running',
  consent_needed: 'contract.consentNeeded',
  done: 'contract.done',
};

function AIWorkspaceHeader({
  onClose,
  conversationId,
  onConversationUpdated,
  onForked,
  mode = 'chat',
  onModeChange,
  agentLifecycleState = 'idle',
}) {
  const { t } = useTranslation('ai');
  const contractKey =
    mode === 'chat'
      ? CONTRACT_TEXT_KEYS.chat
      : CONTRACT_TEXT_KEYS[agentLifecycleState] || CONTRACT_TEXT_KEYS.idle;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        px: 1.5,
        py: 0.75,
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        minHeight: 40,
      }}
    >
      <PulseLogo size={20} showWordmark />
      <Typography
        variant="caption"
        color="text.secondary"
        noWrap
        sx={{
          flex: 1,
          minWidth: 0,
          px: 1,
          fontSize: '0.625rem',
          textAlign: 'center',
        }}
      >
        {t(contractKey)}
      </Typography>
      <ToggleButtonGroup
        exclusive
        size="small"
        value={mode}
        onChange={(event, next) => next && onModeChange?.(next)}
        aria-label={t('pulseMode')}
      >
        <ToggleButton value="chat" aria-label={t('chatMode')}>
          💬 {t('modeChat')}
        </ToggleButton>
        <ToggleButton value="agent" aria-label={t('agentMode')}>
          🤖 {t('modeAgent')}
        </ToggleButton>
      </ToggleButtonGroup>
      <AIContextMenu
        conversationId={conversationId}
        onConversationUpdated={onConversationUpdated}
        onForked={onForked}
      />
      <Tooltip title={t('closePulseShortcut')}>
        <IconButton size="small" onClick={onClose} aria-label={t('closePulse')}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}

AIWorkspaceHeader.propTypes = {
  onClose: PropTypes.func.isRequired,
  conversationId: PropTypes.string,
  onConversationUpdated: PropTypes.func,
  onForked: PropTypes.func,
  mode: PropTypes.oneOf(['chat', 'agent']),
  onModeChange: PropTypes.func,
  agentLifecycleState: PropTypes.oneOf([
    'idle',
    'plan_pending',
    'running',
    'consent_needed',
    'done',
    'error',
  ]),
};

export default AIWorkspaceHeader;
