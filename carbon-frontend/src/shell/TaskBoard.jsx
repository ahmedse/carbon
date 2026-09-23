// Tasks home — needs-you / working / done. No graph until a row is opened.
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import { useTranslation } from 'react-i18next';
import { effectivePlanStatus } from './aiTaskStatus';
import {
  groupTaskBoard,
  humanTaskTitle,
  taskBoardChip,
  taskBoardCoworkerLine,
} from './taskWorkspace';

function Section({ title, count, children, testId }) {
  if (!count) return null;
  return (
    <Box data-testid={testId} sx={{ px: 1.25, pt: 1.25 }}>
      <Typography
        variant="overline"
        color="text.secondary"
        sx={{ fontSize: '0.625rem', letterSpacing: 0.6, display: 'block', mb: 0.5 }}
      >
        {title}
        {' · '}
        {count}
      </Typography>
      <Stack spacing={0.5}>{children}</Stack>
    </Box>
  );
}

function TaskRow({ plan, onSelect, onDelete, deletingId, t }) {
  const status = effectivePlanStatus(plan);
  const chip = taskBoardChip(status);
  const title = humanTaskTitle(plan, t('untitledTask'));
  const full = String(plan?.brief || '').trim() || title;
  return (
    <Box
      role="button"
      tabIndex={0}
      data-testid={`task-board-row-${plan.id}`}
      onClick={() => onSelect(plan.id)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(plan.id);
        }
      }}
      title={full}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        width: '100%',
        textAlign: 'start',
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        bgcolor: 'background.paper',
        px: 1,
        py: 0.75,
        cursor: 'pointer',
        '&:hover': { borderColor: 'text.disabled', bgcolor: 'action.hover' },
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          sx={{
            fontSize: '0.8125rem',
            fontWeight: 500,
            lineHeight: 1.35,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {title}
        </Typography>
      </Box>
      <Chip
        size="small"
        variant="outlined"
        label={t(chip.key)}
        color={chip.color}
        sx={{ height: 18, fontSize: '0.625rem', flexShrink: 0 }}
      />
      {onDelete ? (
        <Tooltip title={t('removeTask')}>
          <IconButton
            size="small"
            aria-label={t('removeTask')}
            onClick={(event) => {
              event.stopPropagation();
              onDelete(plan.id);
            }}
            sx={{ p: 0.25 }}
          >
            <DeleteOutlinedIcon
              sx={{ fontSize: 14, color: deletingId === plan.id ? 'error.main' : 'text.disabled' }}
            />
          </IconButton>
        </Tooltip>
      ) : null}
      <ChevronRightIcon sx={{ fontSize: 16, color: 'text.disabled', flexShrink: 0 }} />
    </Box>
  );
}

function TaskBoard({ plans, loading, loadError, onRetry, onSelect, onDelete, deletingId }) {
  const { t } = useTranslation('ai');
  const groups = useMemo(() => groupTaskBoard(plans), [plans]);
  const total = groups.attention.length + groups.working.length + groups.done.length;
  const coworker = loading && !total
    ? t('boardCoworkerLoading')
    : loadError && !total
      ? t('boardLoadFailed')
      : taskBoardCoworkerLine(groups, t);

  return (
    <Box data-testid="task-board" sx={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 1.25, py: 0.75, borderBottom: 1, borderColor: 'divider' }}
      >
        <Typography
          data-testid="task-board-coworker"
          variant="body2"
          color="text.secondary"
          sx={{ flex: 1, minWidth: 0, fontSize: '0.75rem' }}
        >
          {coworker}
        </Typography>
        {loadError && onRetry ? (
          <Typography
            component="button"
            type="button"
            data-testid="task-board-retry"
            onClick={onRetry}
            sx={{
              border: 0,
              background: 'none',
              p: 0,
              cursor: 'pointer',
              color: 'primary.main',
              fontSize: '0.75rem',
              flexShrink: 0,
            }}
          >
            {t('boardRetry')}
          </Typography>
        ) : null}
      </Stack>

      {loading && !total ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }} data-testid="task-board-loading">
          <CircularProgress size={18} />
        </Box>
      ) : null}

      {total ? (
        <Stack
          direction="row"
          spacing={0.75}
          sx={{ px: 1.25, pt: 1 }}
          data-testid="task-board-summary"
        >
          <Chip size="small" variant="outlined" color="warning" label={`${t('boardNeedsYou')} · ${groups.attention.length}`} sx={{ height: 20, fontSize: '0.625rem' }} />
          <Chip size="small" variant="outlined" color="primary" label={`${t('boardWorking')} · ${groups.working.length}`} sx={{ height: 20, fontSize: '0.625rem' }} />
          <Chip size="small" variant="outlined" label={`${t('boardDone')} · ${groups.done.length}`} sx={{ height: 20, fontSize: '0.625rem' }} />
        </Stack>
      ) : null}

      <Section title={t('boardNeedsYou')} count={groups.attention.length} testId="task-board-attention">
        {groups.attention.map((plan) => (
          <TaskRow key={plan.id} plan={plan} onSelect={onSelect} onDelete={onDelete} deletingId={deletingId} t={t} />
        ))}
      </Section>
      <Section title={t('boardWorking')} count={groups.working.length} testId="task-board-working">
        {groups.working.map((plan) => (
          <TaskRow key={plan.id} plan={plan} onSelect={onSelect} onDelete={onDelete} deletingId={deletingId} t={t} />
        ))}
      </Section>
      <Section title={t('boardDone')} count={groups.done.length} testId="task-board-done">
        {groups.done.map((plan) => (
          <TaskRow key={plan.id} plan={plan} onSelect={onSelect} onDelete={onDelete} deletingId={deletingId} t={t} />
        ))}
      </Section>
    </Box>
  );
}

TaskBoard.propTypes = {
  plans: PropTypes.arrayOf(PropTypes.object),
  loading: PropTypes.bool,
  loadError: PropTypes.bool,
  onRetry: PropTypes.func,
  onSelect: PropTypes.func.isRequired,
  onDelete: PropTypes.func,
  deletingId: PropTypes.string,
};

export default TaskBoard;
