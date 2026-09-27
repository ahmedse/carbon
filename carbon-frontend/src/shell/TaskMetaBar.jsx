// Created / ran / by — always visible on an open task. Not buried in audit.
import React from 'react';
import PropTypes from 'prop-types';
import { Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

dayjs.extend(utc);
dayjs.extend(timezone);

const PROJECT_TIMEZONE = 'Africa/Cairo';

function formatWhen(value) {
  if (!value) return '';
  const parsed = dayjs(value);
  if (!parsed.isValid()) return '';
  return parsed.tz(PROJECT_TIMEZONE).format('MMM D, YYYY · HH:mm');
}

function Fact({ label, value }) {
  if (!value) return null;
  return (
    <Typography
      variant="caption"
      color="text.secondary"
      sx={{ fontSize: '0.6875rem', lineHeight: 1.4 }}
    >
      <Typography
        component="span"
        variant="caption"
        sx={{ fontSize: 'inherit', fontWeight: 600, color: 'text.secondary' }}
      >
        {label}
      </Typography>
      {': '}
      {value}
    </Typography>
  );
}

Fact.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.string,
};

export default function TaskMetaBar({ plan, ledger }) {
  const { t } = useTranslation('ai');
  const created = formatWhen(plan?.created_at);
  const ran = formatWhen(plan?.completed_at || ledger?.provenance?.completed_at);
  const by = (
    plan?.created_by?.display_name
    || ledger?.actor?.display_name
    || ''
  ).trim();

  if (!created && !ran && !by) return null;

  return (
    <Stack
      data-testid="task-meta-bar"
      direction="row"
      flexWrap="wrap"
      columnGap={1.5}
      rowGap={0.25}
      sx={{ px: 1.25, py: 0.5, borderBottom: 1, borderColor: 'divider' }}
    >
      <Fact label={t('taskCreated')} value={created} />
      <Fact label={t('taskRan')} value={ran || (created ? t('taskNotRun') : '')} />
      <Fact label={t('taskBy')} value={by} />
    </Stack>
  );
}

TaskMetaBar.propTypes = {
  plan: PropTypes.object,
  ledger: PropTypes.object,
};
