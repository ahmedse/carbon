// src/pages/admin/ai/control/ProcessObjectPage.jsx
// ADR-0036 Phase 3 — Process object page: structured overview, steps/autonomy,
// scope editor, diff, advanced JSON (draft only). Not a JSON-first drawer.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  Link,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { useNotification } from '../../../../components/NotificationProvider';
import {
  AI_OPERATOR,
  AI_PROCESS_OWNER,
  AI_PUBLISHER,
  hasAnyCap,
} from '../../../../capabilities';
import {
  deprecateProcess,
  getAutonomy,
  getDiff,
  getProcess,
  publishProcess,
  setAutonomy as saveAutonomyDial,
  setKillSwitch,
  submitProcess,
  updateProcess,
} from '../../../../api/aiRegistry';

const AUTONOMY_LEVELS = [
  'observe',
  'propose',
  'act_confirm',
  'act_notify',
  'act_silent',
  'human_only',
];

const SCOPE_SOURCES = [
  'authenticated_host_context',
  'org_unit',
  'role',
  'tenant',
  'global',
];

function capabilityKeys(caps) {
  if (!Array.isArray(caps)) return [];
  return caps
    .map((c) =>
      typeof c === 'string' ? c : c?.key || c?.capability || c?.code || ''
    )
    .filter(Boolean);
}

function statusColor(status, theme) {
  const map = {
    draft: theme.palette.text.secondary,
    review: theme.palette.warning.main,
    active: theme.palette.success.main,
    deprecated: theme.palette.error.main,
  };
  return map[status] || theme.palette.text.secondary;
}

function objectiveText(def) {
  const o = def?.objective;
  if (!o) return '—';
  if (typeof o === 'string') return o;
  if (o && typeof o === 'object' && o.predicate) return o.predicate;
  return JSON.stringify(o);
}

function flattenDiff(added, removed, changed, prefix = '') {
  const out = [];
  for (const key of Object.keys(added || {})) {
    out.push({ kind: 'added', label: prefix ? `${prefix}.${key}` : key });
  }
  for (const key of Object.keys(removed || {})) {
    out.push({ kind: 'removed', label: prefix ? `${prefix}.${key}` : key });
  }
  for (const key of Object.keys(changed || {})) {
    const entry = changed[key];
    const label = prefix ? `${prefix}.${key}` : key;
    if (entry && typeof entry === 'object' && 'from' in entry && 'to' in entry) {
      out.push({ kind: 'changed', label, from: entry.from, to: entry.to });
    } else if (entry && typeof entry === 'object') {
      out.push(...flattenDiff(entry.added, entry.removed, entry.changed, label));
    }
  }
  return out;
}

function GatedButton({ allowed, reason, children, ...props }) {
  const button = (
    <Button {...props} disabled={props.disabled || !allowed}>
      {children}
    </Button>
  );
  if (!allowed) {
    return (
      <Tooltip title={reason || ''}>
        <span>{button}</span>
      </Tooltip>
    );
  }
  return button;
}

function scopeFromDefinition(def) {
  const scope = def?.scope && typeof def.scope === 'object' ? def.scope : {};
  const roles = scope.roles;
  return {
    source: scope.source || 'authenticated_host_context',
    org_unit: scope.org_unit || '',
    roles: Array.isArray(roles) ? roles.join(', ') : roles || '',
    approval_validity: scope.approval_validity || '',
  };
}

function scopeToDocument(form) {
  const roles = form.roles
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const out = {
    source: form.source || 'authenticated_host_context',
  };
  if (form.org_unit.trim()) out.org_unit = form.org_unit.trim();
  if (roles.length) out.roles = roles;
  if (form.approval_validity.trim()) {
    out.approval_validity = form.approval_validity.trim();
  }
  return out;
}

export default function ProcessObjectPage() {
  const { processId } = useParams();
  const navigate = useNavigate();
  const theme = useTheme();
  const { t } = useTranslation('ai');
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();

  useDocumentTitle(
    processId
      ? t('control.processObject.titleWithId', { id: processId })
      : t('control.processObject.title'),
  );

  const caps = useMemo(() => capabilityKeys(userCapabilities), [userCapabilities]);
  const isOwner = useMemo(() => hasAnyCap(caps, [AI_PROCESS_OWNER]), [caps]);
  const isPublisher = useMemo(() => hasAnyCap(caps, [AI_PUBLISHER]), [caps]);
  const canKill = useMemo(
    () => hasAnyCap(caps, [AI_OPERATOR, AI_PROCESS_OWNER]),
    [caps],
  );
  const canDeprecate = useMemo(
    () => hasAnyCap(caps, [AI_PROCESS_OWNER, AI_PUBLISHER]),
    [caps],
  );

  const [tab, setTab] = useState('overview');
  const [detail, setDetail] = useState(null);
  const [diff, setDiff] = useState(null);
  const [autonomyDraft, setAutonomyDraft] = useState({});
  const [scopeForm, setScopeForm] = useState(scopeFromDefinition(null));
  const [objectiveDraft, setObjectiveDraft] = useState('');
  const [jsonDraft, setJsonDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!processId) return;
    setLoading(true);
    setError('');
    try {
      const [d, df, au] = await Promise.all([
        getProcess(token, processId),
        getDiff(token, processId),
        getAutonomy(token, processId),
      ]);
      setDetail(d);
      setDiff(df);
      setAutonomyDraft(au || {});
      setScopeForm(scopeFromDefinition(d?.definition));
      setObjectiveDraft(objectiveText(d?.definition));
      setJsonDraft(JSON.stringify(d?.definition || {}, null, 2));
    } catch (err) {
      setError(err?.detail || err?.message || 'Failed to load process');
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [token, processId]);

  useEffect(() => {
    load();
  }, [load]);

  const steps = Array.isArray(detail?.definition?.steps)
    ? detail.definition.steps
    : [];
  const isDraft = detail?.status === 'draft';

  const runAction = async (fn, args, okMessage) => {
    setActing(true);
    try {
      await fn(...args);
      notify({ message: okMessage, type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Action failed');
    } finally {
      setActing(false);
    }
  };

  const saveAutonomy = () =>
    runAction(
      saveAutonomyDial,
      [token, processId, autonomyDraft],
      'Autonomy dial saved.',
    );

  const saveScopeAndObjective = async () => {
    if (!isDraft) {
      notify({ message: 'Only drafts can edit scope/objective.', type: 'warning' });
      return;
    }
    setActing(true);
    try {
      const merged = {
        ...(detail.definition || {}),
        scope: scopeToDocument(scopeForm),
        objective:
          objectiveDraft.trim().startsWith('{')
            ? JSON.parse(objectiveDraft)
            : { predicate: objectiveDraft.trim() || '—' },
      };
      await updateProcess(token, processId, merged);
      notify({ message: 'Scope and objective saved.', type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Save failed');
    } finally {
      setActing(false);
    }
  };

  const saveJson = async () => {
    if (!isDraft) return;
    setActing(true);
    try {
      const parsed = JSON.parse(jsonDraft);
      await updateProcess(token, processId, parsed);
      notify({ message: 'Definition saved.', type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Invalid JSON or save failed');
    } finally {
      setActing(false);
    }
  };

  if (loading) {
    return (
      <PageContainer>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={24} />
        </Box>
      </PageContainer>
    );
  }

  if (error || !detail) {
    return (
      <PageContainer>
        <Stack spacing={2}>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/admin/ai/domain?tab=processes')}
          >
            Back to registry
          </Button>
          <Typography color="error">{error || 'Process not found'}</Typography>
        </Stack>
      </PageContainer>
    );
  }

  const diffRows = flattenDiff(diff?.added, diff?.removed, diff?.changed);

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
          <Button
            size="small"
            startIcon={<ArrowBackIcon />}
            component={RouterLink}
            to="/admin/ai/domain?tab=processes"
          >
            {t('control.processObject.registry')}
          </Button>
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>
            {detail.process_id}
          </Typography>
          <Chip
            size="small"
            label={detail.status}
            variant="outlined"
            sx={{
              color: statusColor(detail.status, theme),
              borderColor: statusColor(detail.status, theme),
            }}
          />
          <Chip size="small" variant="outlined" label={`v${detail.version}`} />
          <Typography variant="body2" color="text.secondary">
            {detail.owner}
          </Typography>
        </Stack>

        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {detail.status === 'draft' && (
            <GatedButton
              allowed={isOwner}
              reason={t('control.processObject.requiresProcessOwner')}
              size="small"
              variant="contained"
              disabled={acting}
              onClick={() =>
                runAction(
                  submitProcess,
                  [token, processId],
                  t('control.processObject.submitted'),
                )
              }
            >
              {t('control.processObject.submitForReview')}
            </GatedButton>
          )}
          {detail.status === 'review' && (
            <GatedButton
              allowed={isPublisher}
              reason={t('control.processObject.requiresPublisher')}
              size="small"
              variant="contained"
              color="success"
              disabled={acting}
              onClick={() =>
                runAction(
                  publishProcess,
                  [token, processId],
                  t('control.processObject.published'),
                )
              }
            >
              {t('control.processObject.publish')}
            </GatedButton>
          )}
          {detail.status === 'active' && (
            <GatedButton
              allowed={canDeprecate}
              reason={t('control.processObject.requiresOwnerOrPublisher')}
              size="small"
              variant="outlined"
              color="warning"
              disabled={acting}
              onClick={() =>
                runAction(
                  deprecateProcess,
                  [token, processId],
                  t('control.processObject.deprecated'),
                )
              }
            >
              {t('control.processObject.deprecate')}
            </GatedButton>
          )}
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Typography variant="body2">{t('control.processObject.killSwitch')}</Typography>
            <Switch
              size="small"
              checked={Boolean(detail.kill_switch)}
              disabled={!canKill || acting}
              onChange={(e) =>
                runAction(
                  setKillSwitch,
                  [token, processId, e.target.checked],
                  t('control.processObject.killSwitchUpdated'),
                )
              }
            />
          </Stack>
          <Link
            component={RouterLink}
            to={`/admin/ai/evidence?tab=explorer`}
            variant="body2"
          >
            {t('control.processObject.evidence')}
          </Link>
        </Stack>

        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          variant="scrollable"
          scrollButtons="auto"
        >
          <Tab value="overview" label={t('control.processObject.tabOverview')} />
          <Tab value="steps" label={t('control.processObject.tabSteps')} />
          <Tab value="scope" label={t('control.processObject.tabScope')} />
          <Tab value="diff" label={t('control.processObject.tabDiff')} />
          <Tab value="advanced" label={t('control.processObject.tabAdvanced')} />
        </Tabs>

        {tab === 'overview' && (
          <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">
                {t('control.processObject.objective')}
              </Typography>
              <Typography variant="body1">{objectiveText(detail.definition)}</Typography>
            </Paper>
            <Stack direction="row" spacing={2} flexWrap="wrap">
              <Typography variant="body2">
                <strong>{t('control.processObject.stepsCount')}</strong> {steps.length}
              </Typography>
              <Typography variant="body2">
                <strong>{t('control.processObject.evidenceCount')}</strong>{' '}
                {Array.isArray(detail.definition?.evidence)
                  ? detail.definition.evidence.length
                  : 0}
              </Typography>
              <Typography variant="body2">
                <strong>{t('control.processObject.testsCount')}</strong>{' '}
                {Array.isArray(detail.definition?.tests)
                  ? detail.definition.tests.length
                  : 0}
              </Typography>
              <Typography variant="body2">
                <strong>{t('control.processObject.scopeSource')}</strong>{' '}
                {detail.definition?.scope?.source || '—'}
              </Typography>
            </Stack>
            {detail.definition?.last_reject_reason && (
              <Paper variant="outlined" sx={{ p: 1.5 }}>
                <Typography variant="caption" color="warning.main">
                  {t('control.processObject.lastReject')}
                </Typography>
                <Typography variant="body2">
                  {detail.definition.last_reject_reason}
                </Typography>
              </Paper>
            )}
          </Stack>
        )}

        {tab === 'steps' && (
          <Stack spacing={2}>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{t('control.processObject.colStep')}</TableCell>
                    <TableCell>{t('control.processObject.colKind')}</TableCell>
                    <TableCell>{t('control.processObject.colCapability')}</TableCell>
                    <TableCell>{t('control.processObject.colAutonomy')}</TableCell>
                    <TableCell>{t('control.processObject.colConsent')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {steps.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell>{s.id}</TableCell>
                      <TableCell>{s.kind}</TableCell>
                      <TableCell>{s.capability || '—'}</TableCell>
                      <TableCell>
                        <FormControl size="small" sx={{ minWidth: 160 }} disabled={!isOwner}>
                          <InputLabel id={`aut-${s.id}`}>{t('control.processObject.colAutonomy')}</InputLabel>
                          <Select
                            labelId={`aut-${s.id}`}
                            label={t('control.processObject.colAutonomy')}
                            value={autonomyDraft[s.id] || s.autonomy || 'human_only'}
                            onChange={(e) =>
                              setAutonomyDraft((prev) => ({
                                ...prev,
                                [s.id]: e.target.value,
                              }))
                            }
                          >
                            {AUTONOMY_LEVELS.map((level) => (
                              <MenuItem key={level} value={level}>
                                {level}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </TableCell>
                      <TableCell>{s.consent === true ? t('control.processObject.yes') : t('control.processObject.no')}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <GatedButton
              allowed={isOwner}
              reason="Requires ai:process_owner"
              size="small"
              variant="contained"
              onClick={saveAutonomy}
              disabled={acting || !steps.length}
            >
              Save autonomy
            </GatedButton>
          </Stack>
        )}

        {tab === 'scope' && (
          <Stack spacing={2}>
            <Typography variant="body2" color="text.secondary">
              Structured scope editor. Editable on drafts only; active processes
              keep the published scope until a new version.
            </Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <FormControl size="small" sx={{ minWidth: 220 }} disabled={!isDraft || !isOwner}>
                <InputLabel id="scope-source">{t('control.processObject.source')}</InputLabel>
                <Select
                  labelId="scope-source"
                  label={t('control.processObject.source')}
                  value={scopeForm.source}
                  onChange={(e) =>
                    setScopeForm((prev) => ({ ...prev, source: e.target.value }))
                  }
                >
                  {SCOPE_SOURCES.map((s) => (
                    <MenuItem key={s} value={s}>
                      {s}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                size="small"
                label={t('control.processObject.orgUnit')}
                value={scopeForm.org_unit}
                onChange={(e) =>
                  setScopeForm((prev) => ({ ...prev, org_unit: e.target.value }))
                }
                disabled={!isDraft || !isOwner}
                fullWidth
              />
            </Stack>
            <TextField
              size="small"
              label={t('control.processObject.roles')}
              value={scopeForm.roles}
              onChange={(e) =>
                setScopeForm((prev) => ({ ...prev, roles: e.target.value }))
              }
              disabled={!isDraft || !isOwner}
              fullWidth
            />
            <TextField
              size="small"
              label={t('control.processObject.approvalValidity')}
              value={scopeForm.approval_validity}
              onChange={(e) =>
                setScopeForm((prev) => ({
                  ...prev,
                  approval_validity: e.target.value,
                }))
              }
              disabled={!isDraft || !isOwner}
              fullWidth
              helperText="e.g. 72h, session, standing"
            />
            <Divider />
            <TextField
              size="small"
              label={t('control.processObject.objective')}
              value={objectiveDraft}
              onChange={(e) => setObjectiveDraft(e.target.value)}
              disabled={!isDraft || !isOwner}
              fullWidth
              multiline
              minRows={2}
            />
            <GatedButton
              allowed={isOwner && isDraft}
              reason={
                isDraft
                  ? 'Requires ai:process_owner'
                  : 'Only drafts can edit scope/objective'
              }
              size="small"
              variant="contained"
              onClick={saveScopeAndObjective}
              disabled={acting}
            >
              Save scope & objective
            </GatedButton>
          </Stack>
        )}

        {tab === 'diff' && (
          <Paper variant="outlined" sx={{ p: 2 }}>
            {!diff || diff.diff === null ? (
              <Typography variant="body2" color="text.secondary">
                {diff?.reason === 'no_active_version'
                  ? 'No active version to diff against.'
                  : 'No diff available.'}
              </Typography>
            ) : (
              <Stack spacing={1}>
                <Typography variant="body2">
                  {diff.from_version} → {diff.to_version}
                </Typography>
                {diffRows.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No changes vs active.
                  </Typography>
                ) : (
                  diffRows.map((row) => (
                    <Typography key={`${row.kind}-${row.label}`} variant="body2">
                      <Chip size="small" label={row.kind} sx={{ mr: 1 }} />
                      {row.label}
                    </Typography>
                  ))
                )}
              </Stack>
            )}
          </Paper>
        )}

        {tab === 'advanced' && (
          <Stack spacing={1}>
            <Typography variant="body2" color="text.secondary">
              Full definition JSON. Prefer Scope / Steps tabs for normal edits.
              Writable on drafts only.
            </Typography>
            <TextField
              multiline
              fullWidth
              minRows={16}
              maxRows={32}
              value={jsonDraft}
              onChange={(e) => setJsonDraft(e.target.value)}
              disabled={!isDraft || !isOwner}
              sx={{
                '& .MuiInputBase-input': {
                  fontFamily: 'monospace',
                  fontSize: '0.8125rem',
                },
              }}
            />
            <GatedButton
              allowed={isOwner && isDraft}
              reason={
                isDraft
                  ? 'Requires ai:process_owner'
                  : 'Only drafts can edit JSON'
              }
              size="small"
              variant="contained"
              onClick={saveJson}
              disabled={acting}
            >
              Save JSON
            </GatedButton>
          </Stack>
        )}
      </Stack>
    </PageContainer>
  );
}
