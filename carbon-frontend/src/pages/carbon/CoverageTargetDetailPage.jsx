// src/pages/carbon/CoverageTargetDetailPage.jsx
// Coverage target detail — layer 1 (TARGET) with its derived progress and its
// tasks. Progress counts real streams, but this page never claims coverage
// complete: the ratio is labelled "measured, not claimed" and the streams stay
// on the Coverage page (cross-linked, not copied).
//
// Toolkit only: PageContainer, PageHeader, WorkflowCard, EmptyState,
// LoadingSkeleton, Alert+Retry, SearchSelect. RULE 8 tokens, ADR-0037,
// ADR-0018 EN+AR parity.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import FlagIcon from '@mui/icons-material/Flag';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import WorkflowCard from '../../components/Cards/WorkflowCard';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
import { SearchSelect } from '../../components/Form';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchCoverageTarget,
  updateCoverageTarget,
  deleteCoverageTarget,
  createCoverageTask,
  updateCoverageTask,
  deleteCoverageTask,
} from '../../api/emissions-extended';
import {
  EvidenceBadge,
  FieldRow,
  Ltr,
  TargetForm,
  TargetStatusChip,
  TaskStatusChip,
  TaskTypeChip,
  emptyTargetForm,
  formToTargetPayload,
  formatDate,
  goalLabel,
  goalSummary,
  scopeLabel,
  targetToForm,
  useCoverageLookups,
} from './coverageTargetsShared';

const TASK_TYPES = ['bind_data_product', 'complete_rows', 'fill_gap', 'secure_factor', 'other'];
const TASK_STATUSES = ['open', 'in_progress', 'done', 'blocked'];

function taskTypeLabel(t, type) {
  const key = {
    bind_data_product: 'coverageTargets.taskTypeBindDataProduct',
    complete_rows: 'coverageTargets.taskTypeCompleteRows',
    fill_gap: 'coverageTargets.taskTypeFillGap',
    secure_factor: 'coverageTargets.taskTypeSecureFactor',
    other: 'coverageTargets.taskTypeOther',
  }[type];
  return key ? t(key) : (type || '—');
}

function emptyTaskForm() {
  return {
    title: '',
    task_type: 'bind_data_product',
    detail: '',
    status: 'open',
    due_date: '',
    owner: '',
    data_table: '',
    stream_source: '',
    factor: '',
    through_month: '',
  };
}

function taskToForm(task) {
  if (!task) return emptyTaskForm();
  return {
    title: task.title ?? '',
    task_type: task.task_type ?? 'bind_data_product',
    detail: task.detail ?? '',
    status: task.status ?? 'open',
    due_date: task.due_date ?? '',
    owner: task.owner != null ? String(task.owner) : '',
    data_table: task.data_table != null ? String(task.data_table) : '',
    stream_source: task.stream_source != null ? String(task.stream_source) : '',
    factor: task.factor != null ? String(task.factor) : '',
    through_month: task.through_month ?? '',
  };
}

function formToTaskPayload(form, targetId) {
  return {
    target: Number(targetId),
    title: form.title.trim(),
    task_type: form.task_type,
    detail: form.detail || '',
    status: form.status,
    due_date: form.due_date || null,
    owner: form.owner ? Number(form.owner) : null,
    data_table: form.data_table ? Number(form.data_table) : null,
    stream_source: form.stream_source ? Number(form.stream_source) : null,
    factor: form.factor ? Number(form.factor) : null,
    through_month: form.through_month || null,
  };
}

function TaskForm({ values, onField, t }) {
  const { token } = useAuth();
  const lookups = useCoverageLookups(token);
  const set = (name) => (event) => onField(name, event.target.value);
  const type = values.task_type;
  const needsTable = type === 'bind_data_product' || type === 'complete_rows';
  const needsStream = type === 'complete_rows' || type === 'fill_gap';
  const needsFactor = type === 'secure_factor';

  const ownerOptions = useMemo(() => {
    const list = lookups.owners.map((o) => ({
      value: String(o.id),
      label: o.label || o.full_name || o.username || String(o.id),
    }));
    if (values.owner && !list.some((o) => o.value === String(values.owner))) {
      list.unshift({ value: String(values.owner), label: values.owner_name || String(values.owner) });
    }
    return list;
  }, [lookups.owners, values.owner, values.owner_name]);

  return (
    <Stack spacing={2} sx={{ pt: 1 }}>
      <TextField label={t('coverageTargets.taskTitle')} value={values.title} onChange={set('title')} required fullWidth size="small" />
      <SearchSelect
        label={t('coverageTargets.taskType')}
        options={TASK_TYPES.map((value) => ({ value, label: taskTypeLabel(t, value) }))}
        value={type}
        onChange={(option) => onField('task_type', option?.value ?? 'bind_data_product')}
        clearable={false}
      />
      <TextField label={t('coverageTargets.taskDetail')} value={values.detail} onChange={set('detail')} multiline rows={2} fullWidth size="small" />
      {needsTable && (
        <TextField label={t('coverageTargets.taskDataTable')} value={values.data_table} onChange={set('data_table')} type="number" fullWidth size="small" inputProps={{ min: 1 }} />
      )}
      {needsStream && (
        <TextField label={t('coverageTargets.taskStream')} value={values.stream_source} onChange={set('stream_source')} type="number" fullWidth size="small" inputProps={{ min: 1 }} />
      )}
      {needsFactor && (
        <TextField label={t('coverageTargets.taskFactor')} value={values.factor} onChange={set('factor')} type="number" fullWidth size="small" inputProps={{ min: 1 }} />
      )}
      {type === 'complete_rows' && (
        <TextField label={t('coverageTargets.taskThroughMonth')} value={values.through_month} onChange={set('through_month')} type="date" fullWidth size="small" InputLabelProps={{ shrink: true }} />
      )}
      <TextField label={t('coverageTargets.taskDue')} value={values.due_date} onChange={set('due_date')} type="date" fullWidth size="small" InputLabelProps={{ shrink: true }} />
      <SearchSelect
        label={t('coverageTargets.owner')}
        options={ownerOptions}
        value={values.owner}
        onChange={(option) => onField('owner', option?.value ?? '')}
        loading={lookups.ownersState.loading}
        error={lookups.ownersState.error ? t('coverageTargets.ownerLoadError') : undefined}
        onRetry={() => lookups.loadOwners()}
        helperText={t('coverageTargets.ownerHint')}
        placeholder={t('coverageTargets.ownerSearch')}
        noOptionsText={t('coverageTargets.ownerEmpty')}
      />
      <SearchSelect
        label={t('coverageTargets.taskStatus')}
        options={TASK_STATUSES.map((value) => ({
          value,
          label: {
            open: t('coverageTargets.taskOpen'),
            in_progress: t('coverageTargets.taskInProgress'),
            done: t('coverageTargets.taskDone'),
            blocked: t('coverageTargets.taskBlocked'),
          }[value],
        }))}
        value={values.status}
        onChange={(option) => onField('status', option?.value ?? 'open')}
        clearable={false}
      />
    </Stack>
  );
}

const COUNT_CHIPS = [
  ['countRequired', 'required', 'default'],
  ['countEntered', 'entered', 'success'],
  ['countExcluded', 'excluded', 'warning'],
  ['countAwaiting', 'awaiting_factor', 'info'],
  ['countMissing', 'missing', 'error'],
];

export default function CoverageTargetDetailPage() {
  const { targetId } = useParams();
  const { t } = useTranslation('emissions');
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [target, setTarget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState({ target: true, progress: true, tasks: true });

  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState(emptyTargetForm());
  const [saving, setSaving] = useState(false);

  const [taskOpen, setTaskOpen] = useState(false);
  const [taskForm, setTaskForm] = useState(emptyTaskForm());
  const [editingTask, setEditingTask] = useState(null);

  const [confirm, setConfirm] = useState(null); // { kind: 'target' | 'task', id }

  useDocumentTitle(target?.name || 'Coverage target');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchCoverageTarget(targetId, token);
      setTarget(data || null);
    } catch (err) {
      setError(err?.message || t('coverageTargets.loadFailed'));
      setTarget(null);
    } finally {
      setLoading(false);
    }
  }, [targetId, token, t]);

  useEffect(() => {
    load();
  }, [load]);

  const tasks = useMemo(() => (target?.tasks || []), [target]);
  const progress = target?.progress || {};
  const counts = progress.counts || {};

  const toggle = (key) => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const openEdit = () => {
    setForm(targetToForm(target));
    setEditOpen(true);
  };

  const handleTargetField = (name, value) => {
    setForm((prev) => {
      const next = { ...prev, [name]: value };
      if (name === 'goal_kind' && value === 'percent') next.goal_unit = '';
      if (name === 'scope' && !String(value).includes('3')) next.scope3_category = '';
      if (name === 'campus' && String(value) !== String(prev.campus)) next.org_unit = '';
      return next;
    });
  };

  const handleSaveTarget = async () => {
    setSaving(true);
    try {
      await updateCoverageTarget(targetId, formToTargetPayload(form), token);
      notify({ message: t('coverageTargets.updated'), type: 'success' });
      setEditOpen(false);
      await load();
    } catch (err) {
      notifyFromError(err, t('coverageTargets.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const openAddTask = () => {
    setEditingTask(null);
    setTaskForm(emptyTaskForm());
    setTaskOpen(true);
  };

  const openEditTask = (task) => {
    setEditingTask(task);
    setTaskForm(taskToForm(task));
    setTaskOpen(true);
  };

  const handleSaveTask = async () => {
    if (!taskForm.title.trim()) {
      notify({ message: t('coverageTargets.saveTaskFailed'), type: 'error' });
      return;
    }
    setSaving(true);
    try {
      const payload = formToTaskPayload(taskForm, targetId);
      if (editingTask) {
        await updateCoverageTask(editingTask.id, payload, token);
        notify({ message: t('coverageTargets.updatedTask'), type: 'success' });
      } else {
        await createCoverageTask(payload, token);
        notify({ message: t('coverageTargets.createdTask'), type: 'success' });
      }
      setTaskOpen(false);
      await load();
    } catch (err) {
      notifyFromError(err, t('coverageTargets.saveTaskFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleMarkDone = async (task) => {
    try {
      await updateCoverageTask(task.id, { status: 'done' }, token);
      notify({ message: t('coverageTargets.updatedTask'), type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, t('coverageTargets.saveTaskFailed'));
    }
  };

  const handleConfirmDelete = async () => {
    if (!confirm) return;
    try {
      if (confirm.kind === 'target') {
        await deleteCoverageTarget(confirm.id, token);
        notify({ message: t('coverageTargets.deleted'), type: 'success' });
        setConfirm(null);
        navigate('/carbon/admin/coverage-targets');
        return;
      }
      await deleteCoverageTask(confirm.id, token);
      notify({ message: t('coverageTargets.deletedTask'), type: 'success' });
      setConfirm(null);
      await load();
    } catch (err) {
      notifyFromError(err, confirm.kind === 'target' ? t('coverageTargets.deleteFailed') : t('coverageTargets.saveTaskFailed'));
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <LoadingSkeleton variant="detail" />
      </PageContainer>
    );
  }

  if (error || !target) {
    return (
      <PageContainer>
        <PageHeader icon={FlagIcon} title={t('coverageTargets.pageTitle')} />
        <Alert
          severity="error"
          sx={{ mt: 2 }}
          action={(
            <Button color="inherit" size="small" onClick={load}>
              {t('common:retry')}
            </Button>
          )}
        >
          {t('coverageTargets.loadError')}
        </Alert>
        <Box sx={{ mt: 1 }}>
          <Button size="small" startIcon={<ArrowBackIcon />} onClick={() => navigate('/carbon/admin/coverage-targets')}>
            {t('coverageTargets.back')}
          </Button>
        </Box>
      </PageContainer>
    );
  }

  const measuredRatioText = counts.required
    ? t('coverageTargets.measuredRatio', {
      settled: (counts.entered || 0) + (counts.excluded || 0),
      required: counts.required || 0,
      pct: progress.measured_pct ?? '—',
    })
    : t('coverageTargets.emptyProgress');

  return (
    <PageContainer>
      <PageHeader
        icon={FlagIcon}
        title={target.name}
        subtitle={`${target.reporting_period_name || '—'} · ${scopeLabel(target)}`}
        actions={(
          <Button size="small" startIcon={<ArrowBackIcon />} onClick={() => navigate('/carbon/admin/coverage-targets')}>
            {t('coverageTargets.back')}
          </Button>
        )}
      />

      {/* ── Target ─────────────────────────────────────────────── */}
      <WorkflowCard
        icon={<FlagIcon />}
        title={t('coverageTargets.sectionTarget')}
        description={goalSummary(t, target)}
        onClick={() => toggle('target')}
      />
      {expanded.target && (
        <Box data-testid="coverage-target-panel" sx={{ pl: 1, pr: 1, pb: 2, pt: 1.5 }}>
          <Stack spacing={1}>
            <FieldRow label={t('coverageTargets.colCampus')} value={target.campus_name || target.org_unit_name || '—'} />
            <FieldRow label={t('coverageTargets.colOrgUnit')} value={target.org_unit_name || target.org_unit || '—'} />
            <FieldRow label={t('coverageTargets.colScope')} value={<Ltr>{scopeLabel(target)}</Ltr>} />
            <FieldRow label={t('coverageTargets.goalKind')} value={target.goal_kind === 'absolute' ? t('coverageTargets.goalAbsolute') : t('coverageTargets.goalPercent')} />
            <FieldRow label={t('coverageTargets.colGoal')} value={target.goal_kind === 'absolute' ? (<span>{target.goal_value} <Ltr>{target.goal_unit || ''}</Ltr></span>) : goalLabel(target)} />
            <FieldRow label={t('coverageTargets.qualityFloor')} value={target.min_quality_tier != null ? <Ltr>{`T${target.min_quality_tier}`}</Ltr> : t('coverageTargets.qualityFloorNone')} />
            <FieldRow label={t('coverageTargets.dueDate')} value={formatDate(target.due_date)} />
            <FieldRow label={t('coverageTargets.owner')} value={target.owner_name || target.owner_username || '—'} />
            <FieldRow label={t('coverageTargets.colStatus')} value={<TargetStatusChip value={target.status} t={t} />} />
            <FieldRow label={t('coverageTargets.notes')} value={target.notes || '—'} />
          </Stack>
          <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
            <Button size="small" variant="contained" startIcon={<EditIcon />} onClick={openEdit}>
              {t('edit')}
            </Button>
            <Button size="small" color="error" startIcon={<DeleteIcon />} onClick={() => setConfirm({ kind: 'target', id: target.id })}>
              {t('delete')}
            </Button>
          </Stack>
        </Box>
      )}

      {/* ── Progress (measured, not claimed) ───────────────────── */}
      <WorkflowCard
        icon={<CheckCircleIcon />}
        title={t('coverageTargets.sectionProgress')}
        description={measuredRatioText}
        onClick={() => toggle('progress')}
      />
      {expanded.progress && (
        <Box data-testid="coverage-progress-panel" sx={{ pl: 1, pr: 1, pb: 2, pt: 1.5 }}>
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1, mb: 1 }}>
            {COUNT_CHIPS.map(([labelKey, countKey, color]) => (
              <Chip
                key={countKey}
                size="small"
                color={color}
                variant={counts[countKey] ? 'filled' : 'outlined'}
                label={`${t(`coverageTargets.${labelKey}`)}: ${counts[countKey] ?? 0}`}
              />
            ))}
          </Stack>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {measuredRatioText}
          </Typography>
          <Chip size="small" variant="outlined" label={t('coverageTargets.measuredNotClaimed')} sx={{ mt: 0.5 }} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {t('coverageTargets.measuredNotClaimedHint')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {progress.measured_kg != null
              ? t('coverageTargets.measuredKg', { value: progress.measured_kg })
              : t('coverageTargets.measuredKgAbsent')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {t('coverageTargets.countsFromStreams')}
          </Typography>
          <Button
            size="small"
            variant="outlined"
            startIcon={<OpenInNewIcon />}
            sx={{ mt: 1 }}
            onClick={() => navigate('/carbon/admin/inventory-coverage')}
          >
            {t('coverageTargets.crossLinkStreams')}
          </Button>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {t('coverageTargets.crossLinkStreamsHint')}
          </Typography>
        </Box>
      )}

      {/* ── Tasks (done only on host evidence) ─────────────────── */}
      <WorkflowCard
        icon={<CheckCircleIcon />}
        title={t('coverageTargets.sectionTasks')}
        description={`${tasks.filter((task) => task.status === 'done').length}/${tasks.length}`}
        onClick={() => toggle('tasks')}
      />
      {expanded.tasks && (
        <Box data-testid="coverage-tasks-panel" sx={{ pl: 1, pr: 1, pb: 2, pt: 1.5 }}>
          <Stack direction="row" sx={{ justifyContent: 'flex-end', mb: 1 }}>
            <Button size="small" variant="contained" startIcon={<AddIcon />} onClick={openAddTask}>
              {t('coverageTargets.taskAdd')}
            </Button>
          </Stack>
          {tasks.length === 0 ? (
            <EmptyState title={t('coverageTargets.noTasks')} description={t('coverageTargets.noTasksHint')} />
          ) : (
            <Stack spacing={1}>
              {tasks.map((task) => {
                const met = Boolean(task.evidence && task.evidence.met);
                const codes = (task.evidence && task.evidence.codes) || [];
                return (
                  <Paper key={task.id} data-testid="coverage-task" variant="outlined" sx={{ p: 1 }}>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                      <Box sx={{ flex: 1, minWidth: 200 }}>
                        <WorkflowCard
                          icon={<CheckCircleIcon />}
                          title={task.title}
                          description={`${taskTypeLabel(t, task.task_type)} · ${formatDate(task.due_date)}`}
                          onClick={() => openEditTask(task)}
                        />
                      </Box>
                      <TaskTypeChip value={task.task_type} t={t} />
                      <TaskStatusChip value={task.status} t={t} />
                      <EvidenceBadge evidence={task.evidence} t={t} />
                      {!met && codes.length > 0 && (
                        <Typography variant="body2" color="text.secondary">
                          <Ltr>{codes.join(', ')}</Ltr>
                        </Typography>
                      )}
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<CheckCircleIcon />}
                        disabled={task.status === 'done' || !met}
                        onClick={() => handleMarkDone(task)}
                      >
                        {t('coverageTargets.markDone')}
                      </Button>
                      <Button size="small" startIcon={<EditIcon />} onClick={() => openEditTask(task)}>
                        {t('edit')}
                      </Button>
                      <Button size="small" color="error" startIcon={<DeleteIcon />} onClick={() => setConfirm({ kind: 'task', id: task.id })}>
                        {t('delete')}
                      </Button>
                    </Stack>
                  </Paper>
                );
              })}
            </Stack>
          )}
        </Box>
      )}

      <SystemDialog
        open={editOpen}
        title={t('coverageTargets.editTarget')}
        onClose={() => setEditOpen(false)}
        onCancel={() => setEditOpen(false)}
        cancelLabel={t('common:cancel')}
        width={560}
        height={640}
        minWidth={420}
        minHeight={420}
        actions={(
          <Button variant="contained" size="small" onClick={handleSaveTarget} disabled={saving}>
            {t('update')}
          </Button>
        )}
      >
        <TargetForm values={form} onField={handleTargetField} t={t} />
      </SystemDialog>

      <SystemDialog
        open={taskOpen}
        title={editingTask ? t('coverageTargets.taskEdit') : t('coverageTargets.taskNew')}
        onClose={() => setTaskOpen(false)}
        onCancel={() => setTaskOpen(false)}
        cancelLabel={t('common:cancel')}
        width={560}
        height={620}
        minWidth={420}
        minHeight={420}
        actions={(
          <Button variant="contained" size="small" onClick={handleSaveTask} disabled={saving}>
            {editingTask ? t('update') : t('create')}
          </Button>
        )}
      >
        <TaskForm values={taskForm} onField={(name, value) => setTaskForm((prev) => ({ ...prev, [name]: value }))} t={t} />
      </SystemDialog>

      <ConfirmDialog
        open={Boolean(confirm)}
        title={confirm?.kind === 'target' ? t('coverageTargets.deleteTargetTitle') : t('coverageTargets.deleteTaskTitle')}
        message={confirm?.kind === 'target' ? t('coverageTargets.deleteTargetMessage') : t('coverageTargets.deleteTaskMessage')}
        confirmLabel={t('delete')}
        destructive
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirm(null)}
      />
    </PageContainer>
  );
}
