import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  FormControl,
  InputLabel,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Skeleton,
  Stack,
  Switch,
  Tooltip,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  deprecateProcess,
  getAutonomy,
  getProcess,
  listProcesses,
  publishProcess,
  setKillSwitch,
  setAutonomy,
  submitProcess,
} from '../api/aiRegistry';
import { AI_OPERATOR, AI_PROCESS_OWNER, AI_PUBLISHER, hasAnyCap } from '../capabilities';

const STATUS_META = {
  draft: { label: 'Draft', color: 'default' },
  review: { label: 'In review', color: 'warning' },
  active: { label: 'Active', color: 'success' },
  deprecated: { label: 'Retired', color: 'default' },
};

const AUTONOMY_LABELS = {
  human_only: 'Human only',
  observe: 'Observe only',
  propose: 'AI proposes',
  act_confirm: 'AI proposes, human confirms',
  act_notify: 'AI acts, notifies',
  act_silent: 'AI acts automatically',
};

const AUTONOMY_OPTIONS = [
  'human_only',
  'observe',
  'propose',
  'act_confirm',
  'act_notify',
  'act_silent',
];

function toStatusMeta(status) {
  return STATUS_META[status] || { label: 'Unknown', color: 'default' };
}

function toAutonomyLabel(value) {
  return AUTONOMY_LABELS[value] || value || 'Not set';
}

function normalizeProcess(raw) {
  const definition = raw?.definition && typeof raw.definition === 'object' ? raw.definition : raw;
  return {
    processId: raw?.process_id || raw?.id || definition?.id || '',
    version: raw?.version ?? definition?.version ?? 1,
    owner: raw?.owner || definition?.owner || 'Unassigned',
    status: raw?.status || definition?.status || 'draft',
    killSwitch: Boolean(raw?.kill_switch ?? definition?.kill_switch),
    objective: definition?.objective || '',
    policies: Array.isArray(definition?.policies) ? definition.policies : [],
    steps: Array.isArray(definition?.steps) ? definition.steps : [],
  };
}

function getProcessList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  return [];
}

function countHumanGatedSteps(steps) {
  return (steps || []).filter(
    (step) => step?.autonomy === 'human_only' || Boolean(step?.separation_of_duties),
  ).length;
}

function AIProcessesTab() {
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const detailRef = useRef(null);

  const caps = useMemo(() => {
    if (!Array.isArray(userCapabilities)) return [];
    return userCapabilities
      .map((c) => (typeof c === 'string' ? c : c?.key || c?.capability || c?.code || ''))
      .filter(Boolean);
  }, [userCapabilities]);
  const isOwner = useMemo(() => hasAnyCap(caps, [AI_PROCESS_OWNER]), [caps]);
  const isPublisher = useMemo(() => hasAnyCap(caps, [AI_PUBLISHER]), [caps]);
  const canOperate = useMemo(() => hasAnyCap(caps, [AI_OPERATOR, AI_PROCESS_OWNER]), [caps]);
  const canDeprecate = useMemo(() => hasAnyCap(caps, [AI_PROCESS_OWNER, AI_PUBLISHER]), [caps]);

  const [processes, setProcesses] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedProcess, setSelectedProcess] = useState(null);
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState('');
  const [confirmState, setConfirmState] = useState(null);
  const [deniedActions, setDeniedActions] = useState({});

  const markDenied = useCallback((processId, actionKey) => {
    setDeniedActions((prev) => ({
      ...prev,
      [processId]: {
        ...(prev[processId] || {}),
        [actionKey]: true,
      },
    }));
  }, []);

  const isDenied = useCallback(
    (processId, actionKey) => Boolean(deniedActions?.[processId]?.[actionKey]),
    [deniedActions],
  );

  const loadProcesses = useCallback(
    async (preferredId = null) => {
      setListLoading(true);
      setError(null);
      try {
        const data = await listProcesses(token);
        const rows = getProcessList(data).map(normalizeProcess).filter((row) => row.processId);
        setProcesses(rows);

        const preferredExists = preferredId && rows.some((row) => row.processId === preferredId);
        const nextId = preferredExists ? preferredId : rows[0]?.processId || null;
        setSelectedId(nextId);
        return nextId;
      } catch (err) {
        setError(err.message || 'Could not load governed processes');
        notifyFromError(err, 'Could not load governed processes');
        setSelectedId(null);
        setSelectedProcess(null);
        return null;
      } finally {
        setListLoading(false);
      }
    },
    [token, notifyFromError],
  );

  const loadDetail = useCallback(
    async (processId) => {
      if (!processId) {
        setSelectedProcess(null);
        return;
      }
      setDetailLoading(true);
      try {
        const [processData, autonomyData] = await Promise.all([
          getProcess(token, processId),
          getAutonomy(token, processId),
        ]);
        const normalized = normalizeProcess(processData);
        const autonomyMap = autonomyData && typeof autonomyData === 'object' ? autonomyData : {};
        const mergedSteps = normalized.steps.map((step) => ({
          ...step,
          autonomy: autonomyMap[step.id] || step.autonomy,
        }));
        setSelectedProcess({ ...normalized, steps: mergedSteps });
      } catch (err) {
        notifyFromError(err, 'Could not load process details');
      } finally {
        setDetailLoading(false);
      }
    },
    [token, notifyFromError],
  );

  const refreshSelected = useCallback(async () => {
    const nextId = await loadProcesses(selectedId);
    if (nextId) {
      await loadDetail(nextId);
    }
  }, [loadProcesses, loadDetail, selectedId]);

  useEffect(() => {
    loadProcesses();
  }, [loadProcesses]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedProcess(null);
      return;
    }
    loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  useEffect(() => {
    if (selectedProcess && detailRef.current) {
      detailRef.current.focus();
    }
  }, [selectedProcess]);

  const selectedStatus = selectedProcess?.status || '';

  const actionAvailability = useMemo(() => {
    const processId = selectedProcess?.processId;
    if (!processId) {
      return {
        submit: { disabled: true, reason: 'Select a governed process first.' },
        publish: { disabled: true, reason: 'Select a governed process first.' },
        deprecate: { disabled: true, reason: 'Select a governed process first.' },
        kill: { disabled: true, reason: 'Select a governed process first.' },
      };
    }

    const submitDenied = isDenied(processId, 'submit');
    const publishDenied = isDenied(processId, 'publish');
    const deprecateDenied = isDenied(processId, 'deprecate');
    const killDenied = isDenied(processId, 'kill');

    const noCapability = "You don't have the required capability for this action.";

    return {
      submit: {
        disabled: !isOwner || selectedStatus !== 'draft' || submitDenied,
        reason: submitDenied
          ? "You do not have permission for this action."
          : !isOwner
            ? noCapability
            : selectedStatus !== 'draft'
              ? 'Only draft processes can be submitted.'
              : '',
      },
      publish: {
        disabled: !isPublisher || selectedStatus !== 'review' || publishDenied,
        reason: publishDenied
          ? "You do not have permission for this action."
          : !isPublisher
            ? noCapability
            : selectedStatus !== 'review'
              ? 'Only reviewed processes can be activated.'
              : '',
      },
      deprecate: {
        disabled: !canDeprecate || selectedStatus !== 'active' || deprecateDenied,
        reason: deprecateDenied
          ? "You do not have permission for this action."
          : !canDeprecate
            ? noCapability
            : selectedStatus !== 'active'
              ? 'Only active processes can be retired.'
              : '',
      },
      kill: {
        disabled: !canOperate || killDenied,
        reason: killDenied
          ? "You do not have permission for this action."
          : !canOperate
            ? noCapability
            : '',
      },
    };
  }, [selectedProcess, selectedStatus, isDenied, isOwner, isPublisher, canOperate, canDeprecate]);

  const runAction = useCallback(
    async (action, fallbackMessage) => {
      if (!selectedProcess?.processId) return;
      setActionLoading(action);
      try {
        if (action === 'submit') {
          await submitProcess(token, selectedProcess.processId);
          notify({ message: 'Process submitted for review', type: 'success' });
        } else if (action === 'publish') {
          await publishProcess(token, selectedProcess.processId);
          notify({ message: 'Process activated', type: 'success' });
        } else if (action === 'deprecate') {
          await deprecateProcess(token, selectedProcess.processId);
          notify({ message: 'Process retired', type: 'success' });
        } else if (action === 'kill') {
          await setKillSwitch(token, selectedProcess.processId, Boolean(confirmState?.nextKillSwitch));
          notify({
            message: confirmState?.nextKillSwitch
              ? 'Emergency stop enabled'
              : 'Emergency stop disabled',
            type: 'success',
          });
        } else if (action === 'autonomy') {
          await setAutonomy(
            token,
            selectedProcess.processId,
            { [confirmState?.stepId]: confirmState?.nextAutonomy },
          );
          notify({ message: 'Step autonomy updated', type: 'success' });
        }
        await refreshSelected();
      } catch (err) {
        if (err?.status === 403) {
          const denyKey =
            action === 'autonomy' ? `autonomy:${confirmState?.stepId}` : action;
          markDenied(selectedProcess.processId, denyKey);
          notify({ message: "You don't have permission for this action.", type: 'warning' });
        } else {
          notifyFromError(err, fallbackMessage);
        }
      } finally {
        setActionLoading('');
        setConfirmState(null);
      }
    },
    [confirmState, markDenied, notify, notifyFromError, refreshSelected, selectedProcess, token],
  );

  const renderActionButton = (id, label, variant = 'outlined') => {
    const state = actionAvailability[id];
    const disabled = state?.disabled || Boolean(actionLoading);
    return (
      <Tooltip title={state?.reason || ''}>
        <span>
          <Button
            size="small"
            variant={variant}
            disabled={disabled}
            onClick={() => {
              if (id === 'submit') {
                setConfirmState({
                  action: 'submit',
                  title: 'Submit process for review?',
                  body: 'This will move the process from Draft to In review.',
                  confirmLabel: 'Submit for review',
                });
              }
              if (id === 'publish') {
                setConfirmState({
                  action: 'publish',
                  title: 'Activate this process?',
                  body: 'This will make the process Active for governed execution.',
                  confirmLabel: 'Activate',
                });
              }
              if (id === 'deprecate') {
                setConfirmState({
                  action: 'deprecate',
                  title: 'Retire this process?',
                  body: 'This will mark the process as Retired.',
                  confirmLabel: 'Retire',
                });
              }
            }}
            aria-label={label}
          >
            {label}
          </Button>
        </span>
      </Tooltip>
    );
  };

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
        <Typography variant="subtitle2" fontWeight={600} sx={{ flex: 1 }}>
          Governed processes
        </Typography>
        <Button
          size="small"
          startIcon={<RefreshIcon />}
          variant="outlined"
          onClick={refreshSelected}
          aria-label="Refresh governed processes"
        >
          Refresh
        </Button>
      </Stack>

      {listLoading && (
        <Stack spacing={1}>
          <Skeleton variant="rounded" height={40} />
          <Skeleton variant="rounded" height={40} />
          <Skeleton variant="rounded" height={40} />
        </Stack>
      )}

      {!listLoading && error && (
        <Stack spacing={1} alignItems="flex-start">
          <Typography variant="caption" color="error">{error}</Typography>
          <Button size="small" variant="outlined" onClick={refreshSelected}>Retry</Button>
        </Stack>
      )}

      {!listLoading && !error && processes.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            No governed processes yet.
          </Typography>
          <Typography variant="caption" color="text.disabled">
            Publish a process to manage it here.
          </Typography>
        </Box>
      )}

      {!listLoading && !error && processes.length > 0 && (
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems="stretch">
          <Paper variant="outlined" sx={{ width: { xs: '100%', md: 320 }, minWidth: 0 }}>
            <List
              aria-label="Governed processes list"
              role="listbox"
              sx={{ p: 0.5 }}
            >
              {processes.map((process) => {
                const status = toStatusMeta(process.status);
                const stepCount = process.steps.length;
                const humanGated = countHumanGatedSteps(process.steps);
                return (
                  <ListItemButton
                    key={process.processId}
                    selected={selectedId === process.processId}
                    onClick={() => setSelectedId(process.processId)}
                    role="option"
                    aria-selected={selectedId === process.processId}
                    sx={{ borderRadius: 1, mb: 0.5, alignItems: 'flex-start' }}
                  >
                    <ListItemText
                      primary={
                        <Stack direction="row" spacing={0.75} alignItems="center" useFlexGap flexWrap="wrap">
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {process.processId}
                          </Typography>
                          <Chip size="small" label={status.label} color={status.color} />
                        </Stack>
                      }
                      secondary={
                        <Stack spacing={0.25} sx={{ mt: 0.5 }}>
                          <Typography variant="caption" color="text.secondary">
                            {stepCount} steps
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {humanGated} human-gated steps
                          </Typography>
                        </Stack>
                      }
                    />
                  </ListItemButton>
                );
              })}
            </List>
          </Paper>

          <Paper
            ref={detailRef}
            tabIndex={-1}
            variant="outlined"
            sx={{ flex: 1, minWidth: 0, p: 1.5, outline: 'none' }}
            aria-label="Governed process details"
          >
            {detailLoading || !selectedProcess ? (
              <Stack spacing={1}>
                <Skeleton variant="text" width="40%" />
                <Skeleton variant="rounded" height={80} />
                <Skeleton variant="rounded" height={140} />
              </Stack>
            ) : (
              <Stack spacing={1.5}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Typography variant="subtitle2" sx={{ flex: 1 }}>
                    {selectedProcess.processId}
                  </Typography>
                  <Chip
                    size="small"
                    label={toStatusMeta(selectedProcess.status).label}
                    color={toStatusMeta(selectedProcess.status).color}
                  />
                </Stack>

                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                  <Typography variant="caption" color="text.secondary">
                    Version {selectedProcess.version}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Owner: {selectedProcess.owner}
                  </Typography>
                </Stack>

                {selectedProcess.objective ? (
                  <Typography variant="body2" color="text.secondary">
                    {selectedProcess.objective}
                  </Typography>
                ) : null}

                <Divider />

                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ xs: 'stretch', sm: 'center' }}>
                  {renderActionButton('submit', 'Submit for review')}
                  {renderActionButton('publish', 'Activate', 'contained')}
                  {renderActionButton('deprecate', 'Retire')}
                  <Tooltip title={actionAvailability.kill.reason || ''}>
                    <span>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Typography variant="caption" color="text.secondary">
                          Emergency stop
                        </Typography>
                        <Switch
                          size="small"
                          checked={Boolean(selectedProcess.killSwitch)}
                          disabled={actionAvailability.kill.disabled || Boolean(actionLoading)}
                          onChange={(event) => {
                            const nextEnabled = Boolean(event.target.checked);
                            setConfirmState({
                              action: 'kill',
                              title: nextEnabled
                                ? 'Enable emergency stop?'
                                : 'Disable emergency stop?',
                              body: nextEnabled
                                ? 'This pauses automated execution for this process until switched off.'
                                : 'This allows governed execution to continue for this process.',
                              confirmLabel: nextEnabled ? 'Enable stop' : 'Disable stop',
                              nextKillSwitch: nextEnabled,
                            });
                          }}
                          inputProps={{ 'aria-label': 'Toggle emergency stop' }}
                        />
                      </Stack>
                    </span>
                  </Tooltip>
                </Stack>

                <Divider />

                <Typography variant="subtitle2">Process steps</Typography>
                {selectedProcess.steps.length === 0 ? (
                  <Typography variant="caption" color="text.secondary">
                    No configured steps.
                  </Typography>
                ) : (
                  <Stack spacing={1}>
                    {selectedProcess.steps.map((step) => {
                      const autonomyActionKey = `autonomy:${step.id}`;
                      const autonomyDenied = isDenied(selectedProcess.processId, autonomyActionKey);
                      const autonomyDisabled = autonomyDenied || !isOwner || Boolean(actionLoading);
                      const autonomyTooltip = autonomyDenied
                        ? "You do not have permission for this action."
                        : !isOwner
                          ? "You don't have the required capability for this action."
                          : '';
                      return (
                        <Paper key={step.id} variant="outlined" sx={{ p: 1.25 }}>
                          <Stack spacing={0.75}>
                            <Stack direction="row" alignItems="center" spacing={1}>
                              <Typography variant="body2" sx={{ fontWeight: 600, flex: 1 }}>
                                {step.id}
                              </Typography>
                              {step.separation_of_duties ? (
                                <Chip size="small" color="warning" label="Human approval required" />
                              ) : null}
                            </Stack>

                            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                              <Typography variant="caption" color="text.secondary">
                                Kind: {step.kind || 'Not set'}
                              </Typography>
                            </Stack>

                            <Tooltip title={autonomyTooltip}>
                              <span>
                                <FormControl size="small" sx={{ minWidth: 260, maxWidth: 360 }}>
                                  <InputLabel id={`autonomy-${step.id}`}>Autonomy</InputLabel>
                                  <Select
                                    labelId={`autonomy-${step.id}`}
                                    value={step.autonomy || ''}
                                    label="Autonomy"
                                    disabled={autonomyDisabled}
                                    onChange={(event) => {
                                      const nextAutonomy = event.target.value;
                                      if (nextAutonomy === step.autonomy) return;
                                      setConfirmState({
                                        action: 'autonomy',
                                        title: 'Update step autonomy?',
                                        body: `${step.id}: ${toAutonomyLabel(step.autonomy)} -> ${toAutonomyLabel(nextAutonomy)}`,
                                        confirmLabel: 'Update autonomy',
                                        stepId: step.id,
                                        nextAutonomy,
                                      });
                                    }}
                                    inputProps={{
                                      'aria-label': `Autonomy for step ${step.id}`,
                                    }}
                                  >
                                    {AUTONOMY_OPTIONS.map((option) => (
                                      <MenuItem key={option} value={option}>
                                        {toAutonomyLabel(option)}
                                      </MenuItem>
                                    ))}
                                  </Select>
                                </FormControl>
                              </span>
                            </Tooltip>
                          </Stack>
                        </Paper>
                      );
                    })}
                  </Stack>
                )}
              </Stack>
            )}
          </Paper>
        </Stack>
      )}

      <Dialog
        open={Boolean(confirmState)}
        onClose={() => (actionLoading ? null : setConfirmState(null))}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{confirmState?.title}</DialogTitle>
        <DialogContent>
          <DialogContentText>{confirmState?.body}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            size="small"
            onClick={() => setConfirmState(null)}
            disabled={Boolean(actionLoading)}
          >
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            onClick={() => runAction(confirmState?.action, 'Could not update this process')}
            disabled={Boolean(actionLoading)}
          >
            {confirmState?.confirmLabel || 'Confirm'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default AIProcessesTab;