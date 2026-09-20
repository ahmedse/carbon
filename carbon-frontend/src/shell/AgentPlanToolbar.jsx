// src/shell/AgentPlanToolbar.jsx
// ADR-0043 V6 — Plan toolbar under cockpit tabs (actions only).
// Prompt/brief edits happen via Replan or Discuss in Chat — never by clicking
// the label (that was inviting accidental brief mutation).
import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Button,
  Divider,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import AutoFixHighOutlinedIcon from '@mui/icons-material/AutoFixHighOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { isRerunnableStatus } from './aiTaskStatus';
import { useTranslation } from 'react-i18next';

/** Short Operator-facing plan label from brief (first sentence / line). */
export function planDisplayLabel(plan, fallback = 'Untitled plan') {
  const b = String(plan?.brief || '').trim();
  if (!b) return fallback;
  const first = b.split(/\n/)[0].split(/(?<=[.!?])\s+/)[0].trim();
  if (!first) return fallback;
  return first.length > 56 ? `${first.slice(0, 55)}…` : first;
}

/**
 * @param {object} props
 * @param {object} props.plan
 * @param {'review'|'inspect'} [props.mode]
 * @param {boolean} [props.busy]
 * @param {function} props.onApprove
 * @param {function} props.onDecline
 * @param {function} [props.onFork]
 * @param {function} [props.onReplanPlan]
 * @param {function} [props.onDiscuss]
 */
export default function AgentPlanToolbar({
  plan,
  mode = 'review',
  busy = false,
  onApprove,
  onDecline,
  onFork,
  onReplanPlan,
  onDiscuss,
}) {
  const { t } = useTranslation('ai');
  const [editor, setEditor] = useState(null); // 'replan' only
  const [draft, setDraft] = useState(plan?.brief || '');
  const [moreAnchor, setMoreAnchor] = useState(null);
  const cancelled = plan?.status === 'cancelled';
  const running = plan?.status === 'running';
  const inspect = mode === 'inspect';
  const settled = isRerunnableStatus(plan?.status);
  const canReplan = !cancelled && !running && Boolean(onReplanPlan);
  const moreOpen = Boolean(moreAnchor);
  const closeMore = () => setMoreAnchor(null);
  const label = planDisplayLabel(plan, t('untitledPlan'));

  useEffect(() => {
    if (!editor) setDraft(plan?.brief || '');
  }, [plan?.brief, editor]);

  const openReplan = () => {
    setDraft(plan?.brief || '');
    setEditor('replan');
  };

  const saveReplan = () => {
    const next = draft.trim();
    if (!next || !onReplanPlan) return;
    onReplanPlan(next);
    setEditor(null);
  };

  const hasMoreItems = Boolean(onFork || canReplan);

  if (editor === 'replan') {
    return (
      <Stack spacing={0.75} data-testid="agent-brief-editor-replan" sx={{ width: '100%' }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
          {t('replanHint')}
        </Typography>
        {settled && (
          <Typography variant="caption" color="warning.main" sx={{ fontSize: '0.6875rem' }}>
            {t('replanCompletedWarn')}
          </Typography>
        )}
        <TextField
          multiline
          minRows={2}
          maxRows={4}
          fullWidth
          size="small"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          inputProps={{ 'aria-label': t('replanPlan') }}
          sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
          autoFocus
        />
        <Stack direction="row" spacing={0.75}>
          <Button
            size="small"
            variant="contained"
            disabled={busy || !draft.trim()}
            onClick={saveReplan}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            {t('applyReplan')}
          </Button>
          <Button
            size="small"
            variant="text"
            onClick={() => setEditor(null)}
            sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
          >
            {t('cancel')}
          </Button>
        </Stack>
      </Stack>
    );
  }

  return (
    <Toolbar
      disableGutters
      variant="dense"
      data-testid="agent-plan-toolbar"
      sx={{
        width: '100%',
        minHeight: 40,
        gap: 1,
        px: 0,
        flexWrap: 'wrap',
      }}
    >
      <Typography
        data-testid="agent-plan-label"
        sx={{
          flex: '1 1 140px',
          minWidth: 0,
          fontSize: '0.8125rem',
          fontWeight: 600,
          lineHeight: 1.3,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={plan?.brief || label}
      >
        {label}
      </Typography>

      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
        {cancelled ? (
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            {t('planCancelledNothingRan')}
          </Typography>
        ) : inspect ? (
          <Stack direction="row" spacing={0.75} alignItems="center" data-testid="agent-review-inspect">
            {onDiscuss && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<ChatBubbleOutlineIcon sx={{ fontSize: 13 }} />}
                disabled={busy}
                onClick={onDiscuss}
                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
              >
                {t('discussInChat')}
              </Button>
            )}
          </Stack>
        ) : (
          <Stack direction="row" spacing={0.75} alignItems="center" data-testid="agent-review-consent">
            <Button
              size="small"
              variant="contained"
              disabled={busy}
              onClick={onApprove}
              aria-label={t('approvePlan')}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {busy ? t('approvingPlan') : t('approvePlan')}
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="error"
              disabled={busy}
              onClick={onDecline}
              aria-label={t('cancelPlan')}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {t('cancelPlan')}
            </Button>
            {onDiscuss && (
              <Button
                size="small"
                variant="text"
                startIcon={<ChatBubbleOutlineIcon sx={{ fontSize: 13 }} />}
                disabled={busy}
                onClick={onDiscuss}
                sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
              >
                {t('discussInChat')}
              </Button>
            )}
          </Stack>
        )}

        {hasMoreItems && (
          <>
            <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />
            <Tooltip title={t('moreActions')}>
              <IconButton
                size="small"
                aria-label={t('moreActions')}
                aria-haspopup="menu"
                aria-expanded={moreOpen ? 'true' : undefined}
                data-testid="agent-review-more"
                disabled={busy}
                onClick={(e) => setMoreAnchor(e.currentTarget)}
                sx={{ p: 0.375 }}
              >
                <MoreVertIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={moreAnchor}
              open={moreOpen}
              onClose={closeMore}
              data-testid="agent-review-more-menu"
            >
              {onFork && (
                <MenuItem onClick={() => { closeMore(); onFork(); }} disabled={busy}>
                  <ListItemIcon><CallSplitIcon sx={{ fontSize: 16 }} /></ListItemIcon>
                  <ListItemText primaryTypographyProps={{ fontSize: '0.75rem' }}>
                    {t('forkPlan')}
                  </ListItemText>
                </MenuItem>
              )}
              {canReplan && (
                <MenuItem onClick={() => { closeMore(); openReplan(); }} disabled={busy}>
                  <ListItemIcon><AutoFixHighOutlinedIcon sx={{ fontSize: 16 }} /></ListItemIcon>
                  <ListItemText primaryTypographyProps={{ fontSize: '0.75rem' }}>
                    {t('replanPlan')}
                  </ListItemText>
                </MenuItem>
              )}
            </Menu>
          </>
        )}
      </Stack>
    </Toolbar>
  );
}

AgentPlanToolbar.propTypes = {
  plan: PropTypes.object.isRequired,
  mode: PropTypes.oneOf(['review', 'inspect']),
  busy: PropTypes.bool,
  onApprove: PropTypes.func.isRequired,
  onDecline: PropTypes.func.isRequired,
  onFork: PropTypes.func,
  onReplanPlan: PropTypes.func,
  onDiscuss: PropTypes.func,
};
