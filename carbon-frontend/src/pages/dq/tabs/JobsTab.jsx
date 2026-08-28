// carbon-frontend/src/pages/dq/tabs/JobsTab.jsx
import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Drawer,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Cancel, Close, InfoOutlined } from '@mui/icons-material';
import { useAuth } from '../../../auth/AuthContext';
import { useTranslation } from 'react-i18next';
import { useNotification } from '../../../components/NotificationProvider';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { cancelDQJob } from '../../../api/dq';
import { jobTypeLabel, jobStatusLabel, JOB_STATUS_COLORS } from '../constants';

const JOB_TYPES = ['rule_run', 'profile', 'freshness', 'schema', 'nl_check', 'suggest', 'anomaly'];
const JOB_STATUSES = ['queued', 'running', 'done', 'failed', 'canceled'];

function formatDuration(createdAt, updatedAt) {
  if (!createdAt) return '–';
  const end = updatedAt || new Date().toISOString();
  const ms = new Date(end).getTime() - new Date(createdAt).getTime();
  if (!Number.isFinite(ms) || ms < 0) return '–';
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  return `${min}m ${rem}s`;
}

function formatTimestamp(value) {
  if (!value) return '–';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function JobDetailDrawer({ job, onClose, onCancel }) {
  const [canceling, setCanceling] = useState(false);
  const { t } = useTranslation('dq');
  if (!job) return null;
  const resultSummary =
    job.result && typeof job.result === 'object'
      ? {
          status: job.result.status,
          checked_count: job.result.checked_count,
          failed_count: job.result.failed_count,
          score: job.result.score,
          ...(job.result.pulse_task_id ? { pulse_task_id: job.result.pulse_task_id } : {}),
        }
      : job.result;
  return (
    <Drawer anchor="right" open onClose={onClose} PaperProps={{ sx: { width: 440, p: 3 } }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography sx={{ fontSize: '1rem', fontWeight: 700 }}>
          {t('jobs.jobNumber', { id: job.id })}
        </Typography>
        <Button size="small" startIcon={<Close />} onClick={onClose}>
          {t('close')}
        </Button>
      </Stack>
      <Stack spacing={1.5}>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            {t('columns.type')}
          </Typography>
          <Typography>{jobTypeLabel(t, job.job_type)}</Typography>
        </Box>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            {t('columns.status')}
          </Typography>
          <Chip
            size="small"
            color={JOB_STATUS_COLORS[job.status] || 'default'}
            label={jobStatusLabel(t, job.status)}
          />
        </Box>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            {t('columns.target')}
          </Typography>
          <Typography>
            {job.rule_name ? t('jobs.ruleTarget', { name: job.rule_name, id: job.rule ?? '–' }) : ''}
            {job.rule_name && job.table_name ? ' · ' : ''}
            {job.table_name ? t('jobs.tableTarget', { name: job.table_name, id: job.data_table ?? '–' }) : ''}
            {!job.rule_name && !job.table_name ? '–' : ''}
          </Typography>
        </Box>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            {t('columns.created')}
          </Typography>
          <Typography>
            {t('jobs.createdBy', {
              timestamp: formatTimestamp(job.created_at),
              name: job.created_by_name || t('jobs.system'),
            })}
          </Typography>
        </Box>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            {t('columns.duration')}
          </Typography>
          <Typography>
            {formatDuration(job.created_at, job.updated_at)}
          </Typography>
        </Box>
        {job.pulse_task_id ? (
          <Box>
            <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
              {t('jobs.pulseTask')}
            </Typography>
            <Typography sx={{ fontFamily: 'monospace' }}>{job.pulse_task_id}</Typography>
          </Box>
        ) : null}
        {job.error ? (
          <Box>
            <Typography sx={{ color: 'error.main', textTransform: 'uppercase' }}>
              {t('columns.error')}
            </Typography>
            <Typography sx={{ color: 'error.main' }}>{job.error}</Typography>
          </Box>
        ) : null}
        {resultSummary ? (
          <Box>
            <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
              {t('columns.result')}
            </Typography>
            <Box
              component="pre"
              sx={{
                p: 1.5,
                borderRadius: 1,
                bgcolor: 'action.hover',
                overflow: 'auto',
                maxHeight: 240,
                m: 0,
              }}
            >
              {JSON.stringify(resultSummary, null, 2)}
            </Box>
          </Box>
        ) : null}
        {job.payload ? (
          <Box>
            <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
              {t('columns.payload')}
            </Typography>
            <Box
              component="pre"
              sx={{
                p: 1.5,
                borderRadius: 1,
                bgcolor: 'action.hover',
                overflow: 'auto',
                maxHeight: 240,
                m: 0,
              }}
            >
              {JSON.stringify(job.payload, null, 2)}
            </Box>
          </Box>
        ) : null}
        {(job.status === 'queued' || job.status === 'running') && (
          <Button
            variant="outlined"
            color="error"
            startIcon={<Cancel />}
            disabled={canceling}
            onClick={async () => {
              setCanceling(true);
              try {
                await onCancel(job);
              } finally {
                setCanceling(false);
              }
            }}
          >
            {t('jobs.cancelJob')}
          </Button>
        )}
      </Stack>
    </Drawer>
  );
}

function JobsTab({ jobs, loading, reload }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const { t } = useTranslation('dq');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selected, setSelected] = useState(null);

  const filtered = useMemo(() => {
    return (jobs || []).filter(
      (job) =>
        (!statusFilter || job.status === statusFilter) &&
        (!typeFilter || job.job_type === typeFilter)
    );
  }, [jobs, statusFilter, typeFilter]);

  const handleCancel = async (job) => {
    try {
      await cancelDQJob(token, job.id);
      notify({ message: t('jobs.cancelRequested', { id: job.id }), type: 'info' });
      setSelected(null);
      reload();
    } catch (err) {
      notifyFromError(err, t('jobs.cancelError'));
    }
  };

  const columns = useMemo(
    () => [
      { field: 'id', headerName: t('columns.id'), width: 60 },
      {
        field: 'job_type',
        headerName: t('columns.type'),
        width: 150,
        renderCell: ({ row }) => (
          <Chip size="small" variant="outlined" label={jobTypeLabel(t, row.job_type)} />
        ),
      },
      {
        field: 'target',
        headerName: t('columns.target'),
        flex: 1.4,
        minWidth: 200,
        renderCell: ({ row }) => {
          const label = row.rule_name || row.table_name || '–';
          return (
            <Stack spacing={0.25}>
              <Typography>{label}</Typography>
              {row.rule && row.table_name ? (
                <Typography sx={{ color: 'text.secondary' }}>
                  {t('jobs.ruleTableRef', { rule: row.rule, table: row.data_table })}
                </Typography>
              ) : null}
            </Stack>
          );
        },
      },
      {
        field: 'status',
        headerName: t('columns.status'),
        width: 120,
        renderCell: ({ row }) => (
          <Chip size="small" color={JOB_STATUS_COLORS[row.status] || 'default'} label={jobStatusLabel(t, row.status)} />
        ),
      },
      {
        field: 'progress',
        headerName: t('columns.progress'),
        width: 140,
        renderCell: ({ row }) => {
          if (row.status === 'running') {
            const value = Number(row.progress) || 0;
            return <LinearProgress variant="determinate" value={value} sx={{ width: '100%' }} />;
          }
          if (row.status === 'queued') {
            return <LinearProgress sx={{ width: '100%' }} />;
          }
          return (
            <Typography sx={{ color: 'text.secondary' }}>
              {row.status === 'done' ? '100%' : '–'}
            </Typography>
          );
        },
      },
      {
        field: 'created_at',
        headerName: t('columns.created'),
        width: 150,
        valueGetter: (_value, row) => formatTimestamp(row.created_at),
      },
      {
        field: 'duration',
        headerName: t('columns.duration'),
        width: 90,
        valueGetter: (_value, row) => formatDuration(row.created_at, row.updated_at),
      },
      {
        field: 'created_by_name',
        headerName: t('columns.by'),
        width: 110,
        valueGetter: (_value, row) => row.created_by_name || t('jobs.system'),
      },
    ],
    [t]
  );

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label={t('columns.status')}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          sx={{ minWidth: 130 }}
        >
          <MenuItem value="">{t('all')}</MenuItem>
          {JOB_STATUSES.map((s) => (
            <MenuItem key={s} value={s}>
              {jobStatusLabel(t, s)}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label={t('columns.type')}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          sx={{ minWidth: 170 }}
        >
          <MenuItem value="">{t('all')}</MenuItem>
          {JOB_TYPES.map((jt) => (
            <MenuItem key={jt} value={jt}>
              {jobTypeLabel(t, jt)}
            </MenuItem>
          ))}
        </TextField>
        <Box sx={{ flexGrow: 1 }} />
        <Button size="small" variant="outlined" onClick={reload}>
          {t('refresh')}
        </Button>
      </Stack>

      <CarbonDataGrid
        columns={columns}
        rows={filtered}
        loading={loading}
        getRowId={(row) => row.id}
        emptyMessage={t('jobs.empty')}
        onRowClick={({ row }) => setSelected(row)}
      />

      {selected ? (
        <JobDetailDrawer job={selected} onClose={() => setSelected(null)} onCancel={handleCancel} />
      ) : null}
    </Box>
  );
}

JobsTab.propTypes = {
  jobs: PropTypes.array,
  loading: PropTypes.bool,
  reload: PropTypes.func.isRequired,
};

export default JobsTab;
