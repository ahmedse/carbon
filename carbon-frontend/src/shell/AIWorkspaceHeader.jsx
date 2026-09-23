// src/shell/AIWorkspaceHeader.jsx
// W5-A (ADR-0014) — Chat and Agent are the two top-level Pulse modes. Mode
// lives HERE (workspace level), not in the composer. The always-visible
// safety-contract text sits beside the mode buttons and changes with the
// agent lifecycle so the trust contract is legible at all times.
// RULE_8: theme tokens only (no hex/raw px). RULE_3: compact density.
// G3 — Checkpoint buttons: ⊕ saves a named snapshot, ↩ opens CheckpointPicker.

import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Chip,
  IconButton,
  Snackbar,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import CloseIcon from '@mui/icons-material/Close';
import OpenInFullIcon from '@mui/icons-material/OpenInFull';
import CloseFullscreenIcon from '@mui/icons-material/CloseFullscreen';
import RestoreOutlinedIcon from '@mui/icons-material/RestoreOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { createCheckpoint } from '../api/aiWorkspace';
import { AI_MANAGE_CONSOLE, expandCapabilities, hasCap } from '../capabilities';
import PulseLogo from './PulseLogo';
import AIContextMenu from './AIContextMenu';
import CheckpointPicker from './CheckpointPicker';
import { isPulseAgentUiEnabled } from './pulseAgentUi';

function capabilityKeys(caps) {
  if (!Array.isArray(caps)) return [];
  return caps
    .map((c) => (typeof c === 'string' ? c : c?.key || c?.capability))
    .filter(Boolean);
}

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
  expanded = false,
  onToggleExpand,
  conversationId,
  onConversationUpdated,
  onForked,
  mode = 'chat',
  onModeChange,
  agentLifecycleState = 'idle',
  linkedPlan = null,
  onOpenLinkedPlan,
  onDismissLinkedPlan,
}) {
  const { t } = useTranslation('ai');
  const { token, userCapabilities } = useAuth();
  const { notifyFromError } = useNotification();
  const canManageConsole = useMemo(
    () => hasCap(expandCapabilities(capabilityKeys(userCapabilities)), AI_MANAGE_CONSOLE),
    [userCapabilities],
  );
  const [pickerOpen, setPickerOpen] = useState(false);
  const [snackbar, setSnackbar] = useState(null); // { message }
  const agentUiOn = isPulseAgentUiEnabled();

  const contractKey =
    mode === 'chat'
      ? CONTRACT_TEXT_KEYS.chat
      : CONTRACT_TEXT_KEYS[agentLifecycleState] || CONTRACT_TEXT_KEYS.idle;

  const linkedBrief = (linkedPlan?.brief || '').trim();
  const showContinuityChip = mode === 'chat' && Boolean(linkedPlan?.id || linkedBrief);
  const linkedLabel = linkedBrief
    ? t('continuity.openPlan', {
      brief: linkedBrief.length > 36 ? `${linkedBrief.slice(0, 36)}…` : linkedBrief,
    })
    : t('continuity.continueInAgent');

  const handleSaveCheckpoint = async () => {
    if (!conversationId || !canManageConsole) return;
    const now = new Date();
    const name = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      + ' · '
      + now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    try {
      await createCheckpoint(token, conversationId, name);
      setSnackbar({ message: t('checkpointSaved', { name }) });
    } catch (err) {
      notifyFromError(err, t('checkpointSaveFailed'));
    }
  };

  return (
    <>
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
        {showContinuityChip ? (
          <Chip
            size="small"
            color="primary"
            variant="outlined"
            icon={<TaskAltOutlinedIcon sx={{ fontSize: '14px !important' }} />}
            label={linkedLabel}
            onClick={() => onOpenLinkedPlan?.()}
            onDelete={onDismissLinkedPlan ? () => onDismissLinkedPlan() : undefined}
            data-testid="chat-agent-continuity-chip"
            sx={{
              mx: 0.75,
              maxWidth: 220,
              height: 24,
              fontSize: '0.625rem',
              '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' },
            }}
          />
        ) : null}
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
        {agentUiOn ? (
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
        ) : null}
        {canManageConsole ? (
          <>
            <Tooltip title={t('saveCheckpoint')}>
              <span>
                <IconButton
                  size="small"
                  onClick={handleSaveCheckpoint}
                  disabled={!conversationId}
                  aria-label={t('saveCheckpoint')}
                  sx={{ p: 0.5 }}
                >
                  <AddCircleOutlineIcon sx={{ fontSize: 15 }} />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title={t('checkpoints')}>
              <span>
                <IconButton
                  size="small"
                  onClick={() => setPickerOpen(true)}
                  disabled={!conversationId}
                  aria-label={t('openCheckpoints')}
                  sx={{ p: 0.5 }}
                >
                  <RestoreOutlinedIcon sx={{ fontSize: 15 }} />
                </IconButton>
              </span>
            </Tooltip>
          </>
        ) : null}
        <AIContextMenu
          conversationId={conversationId}
          onConversationUpdated={onConversationUpdated}
          onForked={onForked}
        />
        {typeof onToggleExpand === 'function' && (
          <Tooltip title={expanded ? t('dockPulseShortcut') : t('expandPulseShortcut')}>
            <IconButton
              size="small"
              onClick={onToggleExpand}
              aria-label={expanded ? t('dockPulse') : t('expandPulse')}
              aria-pressed={expanded}
              sx={{ p: 0.5 }}
            >
              {expanded ? (
                <CloseFullscreenIcon sx={{ fontSize: 15 }} />
              ) : (
                <OpenInFullIcon sx={{ fontSize: 15 }} />
              )}
            </IconButton>
          </Tooltip>
        )}
        <Tooltip title={t('closePulseShortcut')}>
          <IconButton size="small" onClick={onClose} aria-label={t('closePulse')}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      {canManageConsole ? (
        <CheckpointPicker
          conversationId={conversationId}
          open={pickerOpen}
          onClose={() => setPickerOpen(false)}
          onFork={onForked}
        />
      ) : null}
      <Snackbar
        open={Boolean(snackbar)}
        message={snackbar?.message}
        autoHideDuration={4000}
        onClose={() => setSnackbar(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </>
  );
}

AIWorkspaceHeader.propTypes = {
  onClose: PropTypes.func.isRequired,
  expanded: PropTypes.bool,
  onToggleExpand: PropTypes.func,
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
  linkedPlan: PropTypes.shape({
    id: PropTypes.string,
    brief: PropTypes.string,
    status: PropTypes.string,
  }),
  onOpenLinkedPlan: PropTypes.func,
  onDismissLinkedPlan: PropTypes.func,
};

export default AIWorkspaceHeader;
