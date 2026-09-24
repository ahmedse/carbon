// AgentResultToolbar — Result chrome under cockpit tabs (ADR-0043 V11).
// ≤3 visible: host CTA · Discuss · Rerun · More (Open Plan · exports).
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Button,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Tooltip,
} from '@mui/material';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DataObjectOutlinedIcon from '@mui/icons-material/DataObjectOutlined';
import { Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

/**
 * @param {object} props
 * @param {Array<{route:string,label:string,summary?:string}>} [props.hostActions]
 * @param {boolean} [props.rerunnable]
 * @param {boolean} [props.busy]
 * @param {boolean} [props.canExportLedger]
 * @param {boolean} [props.canExportResponse]
 * @param {function} [props.onRerun]
 * @param {function} [props.onDiscuss]
 * @param {function} [props.onOpenPlan]
 * @param {function} [props.onExportLedger]
 * @param {function} [props.onExportResponse]
 */
export default function AgentResultToolbar({
  hostActions = [],
  rerunnable = false,
  busy = false,
  canExportLedger = false,
  canExportResponse = false,
  onRerun,
  onDiscuss,
  onOpenPlan,
  onExportLedger,
  onExportResponse,
}) {
  const { t } = useTranslation('ai');
  const [anchor, setAnchor] = useState(null);
  const primary = hostActions[0] || null;
  const moreHost = hostActions.slice(1);

  return (
    <Toolbar
      disableGutters
      variant="dense"
      data-testid="agent-result-toolbar"
      sx={{
        width: '100%',
        minHeight: 32,
        gap: 1,
        px: 0,
        flexWrap: 'wrap',
        alignItems: 'center',
        py: 0.25,
      }}
    >
      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
        {primary ? (
          <Button
            size="small"
            variant="contained"
            component={RouterLink}
            to={primary.route}
            data-testid="result-primary-cta"
            sx={{ textTransform: 'none' }}
          >
            {primary.label}
          </Button>
        ) : null}
        {onDiscuss ? (
          <Button
            size="small"
            variant={primary ? 'outlined' : 'contained'}
            startIcon={<ChatBubbleOutlineIcon sx={{ fontSize: 13 }} />}
            disabled={busy}
            onClick={onDiscuss}
            sx={{ textTransform: 'none' }}
          >
            {t('discussInChat')}
          </Button>
        ) : null}
        {onRerun ? (
          <Tooltip title={rerunnable ? t('rerunPlan') : t('resultRerunNeedsApprove')}>
            <span>
              <Button
                size="small"
                variant="outlined"
                disabled={!rerunnable || busy}
                onClick={onRerun}
                sx={{ textTransform: 'none' }}
              >
                {t('rerunPlanShort')}
              </Button>
            </span>
          </Tooltip>
        ) : null}
        <IconButton
          size="small"
          aria-label={t('resultMoreActions')}
          aria-haspopup="menu"
          aria-expanded={Boolean(anchor)}
          onClick={(e) => setAnchor(e.currentTarget)}
          data-testid="result-more-menu"
        >
          <MoreVertIcon sx={{ fontSize: 18 }} />
        </IconButton>
        <Menu
          anchorEl={anchor}
          open={Boolean(anchor)}
          onClose={() => setAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          {moreHost.map((action) => (
            <MenuItem
              key={action.route}
              component={RouterLink}
              to={action.route}
              onClick={() => setAnchor(null)}
            >
              <ListItemText primary={action.label} secondary={action.summary || undefined} />
            </MenuItem>
          ))}
          {onOpenPlan ? (
            <MenuItem
              onClick={() => {
                setAnchor(null);
                onOpenPlan();
              }}
            >
              <ListItemIcon><EditOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText>{t('openPlanToEdit')}</ListItemText>
            </MenuItem>
          ) : null}
          {onExportLedger ? (
            <MenuItem
              disabled={!canExportLedger}
              onClick={() => {
                setAnchor(null);
                onExportLedger();
              }}
            >
              <ListItemIcon><DataObjectOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText>{t('resultExportLedger')}</ListItemText>
            </MenuItem>
          ) : null}
          {onExportResponse ? (
            <MenuItem
              disabled={!canExportResponse}
              onClick={() => {
                setAnchor(null);
                onExportResponse();
              }}
            >
              <ListItemIcon><DescriptionOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText>{t('resultExportResponse')}</ListItemText>
            </MenuItem>
          ) : null}
        </Menu>
      </Stack>
    </Toolbar>
  );
}

AgentResultToolbar.propTypes = {
  hostActions: PropTypes.arrayOf(PropTypes.shape({
    route: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    summary: PropTypes.string,
  })),
  rerunnable: PropTypes.bool,
  busy: PropTypes.bool,
  canExportLedger: PropTypes.bool,
  canExportResponse: PropTypes.bool,
  onRerun: PropTypes.func,
  onDiscuss: PropTypes.func,
  onOpenPlan: PropTypes.func,
  onExportLedger: PropTypes.func,
  onExportResponse: PropTypes.func,
};
