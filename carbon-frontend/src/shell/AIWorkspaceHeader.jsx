// src/shell/AIWorkspaceHeader.jsx
// W5-A (ADR-0014) — Chat and Agent are the two top-level Pulse modes. Mode
// lives HERE (workspace level), not in the composer. The always-visible
// safety-contract text sits beside the mode buttons and changes with the
// agent lifecycle so the trust contract is legible at all times.
// RULE_8: theme tokens only (no hex/raw px). RULE_3: compact density.

import React from 'react';
import PropTypes from 'prop-types';
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
const CONTRACT_TEXT = {
  chat: '💬 Chat — Answers and advice only. Nothing is created or changed.',
  idle: '🤖 Agent — Describe an outcome. The AI will plan before doing anything.',
  plan_pending: '🤖 Agent — Review the plan. Nothing runs until you approve.',
  running: '🤖 Agent ● Running — Step N of M · Pause anytime.',
  consent_needed: '🤖 Agent ⏸ Approval needed — A step requires your confirmation.',
  done: '🤖 Agent ✓ Done — Results are ready.',
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
  const contractText =
    mode === 'chat' ? CONTRACT_TEXT.chat : CONTRACT_TEXT[agentLifecycleState] || CONTRACT_TEXT.idle;

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
        {contractText}
      </Typography>
      <ToggleButtonGroup
        exclusive
        size="small"
        value={mode}
        onChange={(event, next) => next && onModeChange?.(next)}
        aria-label="Pulse mode"
      >
        <ToggleButton value="chat" aria-label="Chat mode">
          💬 Chat
        </ToggleButton>
        <ToggleButton value="agent" aria-label="Agent mode">
          🤖 Agent
        </ToggleButton>
      </ToggleButtonGroup>
      <AIContextMenu
        conversationId={conversationId}
        onConversationUpdated={onConversationUpdated}
        onForked={onForked}
      />
      <Tooltip title="Close Pulse (Ctrl+\)">
        <IconButton size="small" onClick={onClose} aria-label="Close Pulse">
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
