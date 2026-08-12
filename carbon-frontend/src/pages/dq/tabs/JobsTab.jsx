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
import { useNotification } from '../../../components/NotificationProvider';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { cancelDQJob } from '../../../api/dq';
import { JOB_TYPE_LABELS, JOB_STATUS_LABELS, JOB_STATUS_COLORS } from '../constants';

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
        <Typography sx={{ fontSize: '1rem', fontWeight: 700 }}>Job #{job.id}</Typography>
        <Button size="small" startIcon={<Close />} onClick={onClose}>
          Close
        </Button>
      </Stack>
      <Stack spacing={1.5}>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            Type
          </Typography>
          <Typography>{JOB_TYPE_LABELS[job.job_type] || job.job_type}</Typography>
        </Box>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            Status
          </Typography>
          <Chip
            size="small"
            color={JOB_STATUS_COLORS[job.status] || 'default'}
            label={JOB_STATUS_LABELS[job.status] || job.status}
          />
        </Box>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            Target
          </Typography>
          <Typography>
            {job.rule_name ? `Rule: ${job.rule_name} (${job.rule ?? '–'})` : ''}
            {job.rule_name && job.table_name ? ' · ' : ''}
            {job.table_name ? `Table: ${job.table_name} (${job.data_table ?? '–'})` : ''}
            {!job.rule_name && !job.table_name ? '–' : ''}
          </Typography>
        </Box>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            Created
          </Typography>
          <Typography>
            {formatTimestamp(job.created_at)} by {job.created_by_name || 'system'}
          </Typography>
        </Box>
        <Box>
          <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
            Duration
          </Typography>
          <Typography>
            {formatDuration(job.created_at, job.updated_at)}
          </Typography>
        </Box>
        {job.pulse_task_id ? (
          <Box>
            <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
              Pulse Task
            </Typography>
            <Typography sx={{ fontFamily: 'monospace' }}>{job.pulse_task_id}</Typography>
          </Box>
        ) : null}
        {job.error ? (
          <Box>
            <Typography sx={{ color: 'error.main', textTransform: 'uppercase' }}>
              Error
            </Typography>
            <Typography sx={{ color: 'error.main' }}>{job.error}</Typography>
          </Box>
        ) : null}
        {resultSummary ? (
          <Box>
            <Typography sx={{ color: 'text.secondary', textTransform: 'uppercase' }}>
              Result
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
              Payload
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
            Cancel job
          </Button>
        )}
      </Stack>
    </Drawer>
  );
}

function JobsTab({ jobs, loading, reload }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
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
      notify({ message: `Job #${job.id} cancel requested`, type: 'info' });
      setSelected(null);
      reload();
    } catch (err) {
      notifyFromError(err, 'Could not cancel job');
    }
  };

  const columns = useMemo(
    () => [
      { field: 'id', headerName: 'ID', width: 60 },
      {
        field: 'job_type',
        headerName: 'Type',
        width: 150,
        renderCell: ({ row }) => (
          <Chip size="small" variant="outlined" label={JOB_TYPE_LABELS[row.job_type] || row.job_type} />
        ),
      },
      {
        field: 'target',
        headerName: 'Target',
        flex: 1.4,
        minWidth: 200,
        renderCell: ({ row }) => {
          const label = row.rule_name || row.table_name || '–';
          return (
            <Stack spacing={0.25}>
              <Typography>{label}</Typography>
              {row.rule && row.table_name ? (
                <Typography sx={{ color: 'text.secondary' }}>
                  rule #{row.rule} · table #{row.data_table}
                </Typography>
              ) : null}
            </Stack>
          );
        },
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        renderCell: ({ row }) => (
          <Chip size="small" color={JOB_STATUS_COLORS[row.status] || 'default'} label={JOB_STATUS_LABELS[row.status] || row.status} />
        ),
      },
      {
        field: 'progress',
        headerName: 'Progress',
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
        headerName: 'Created',
        width: 150,
        valueGetter: (_value, row) => formatTimestamp(row.created_at),
      },
      {
        field: 'duration',
        headerName: 'Duration',
        width: 90,
        valueGetter: (_value, row) => formatDuration(row.created_at, row.updated_at),
      },
      {
        field: 'created_by_name',
        headerName: 'By',
        width: 110,
        valueGetter: (_value, row) => row.created_by_name || 'system',
      },
    ],
    []
  );

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          sx={{ minWidth: 130 }}
        >
          <MenuItem value="">All</MenuItem>
          {JOB_STATUSES.map((s) => (
            <MenuItem key={s} value={s}>
              {JOB_STATUS_LABELS[s] || s}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Type"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          sx={{ minWidth: 170 }}
        >
          <MenuItem value="">All</MenuItem>
          {JOB_TYPES.map((t) => (
            <MenuItem key={t} value={t}>
              {JOB_TYPE_LABELS[t] || t}
            </MenuItem>
          ))}
        </TextField>
        <Box sx={{ flexGrow: 1 }} />
        <Button size="small" variant="outlined" onClick={reload}>
          Refresh
        </Button>
      </Stack>

      <CarbonDataGrid
        columns={columns}
        rows={filtered}
        loading={loading}
        getRowId={(row) => row.id}
        emptyMessage="No jobs yet — run a rule or trigger Pulse from the Suggestions tab"
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
