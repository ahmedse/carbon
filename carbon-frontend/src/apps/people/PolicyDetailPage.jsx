// src/apps/people/PolicyDetailPage.jsx
// People & Payroll — Leave Policy 360 detail (LPR-1B). Six tabs over a single
// policy fetched from /people/leave-policies/:id. Tabs persist to localStorage
// (RULE_17). Employees tab drives dry-run preview → confirm propagation.

import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import PolicyIcon from '@mui/icons-material/Policy';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PublishIcon from '@mui/icons-material/Publish';
import AddIcon from '@mui/icons-material/Add';
import { useAuth } from '../../auth/AuthContext';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import { fetchLeavePolicy, propagateLeavePolicy, fetchLeavePolicyVersions, forkLeavePolicy } from '../../api/people';
import { formatDate } from './utils';
import { FONT } from '../../theme/themeTokens';

const STORAGE_KEY = 'carbon-people-policy-detail-tab';
const TAB_KEYS = ['General', 'Entitlement', 'Carryover', 'Eligibility', 'Workflow', 'Employees', 'Versions'];

// Configurable policy fields and their i18n labels for rendering version snapshots.
const SNAPSHOT_LABELS = {
  name: 'colName',
  description: 'colDescription',
  leave_type: 'colLeaveType',
  status: 'colStatus',
  default_entitled_days: 'colDefaultDays',
  accrual_method: 'colAccrual',
  max_carryover_days: 'colMaxCarryover',
  is_carryover_allowed: 'colCarryoverAllowed',
  gender_restriction: 'colGender',
  min_service_days: 'colMinService',
  applies_to_org_units: 'colAppliesToOrgUnits',
  applies_to_contract_types: 'colAppliesToContractTypes',
  requires_approval: 'colRequiresApproval',
  notes: 'colNotes',
  effective_from: 'colEffectiveFrom',
  effective_to: 'colEffectiveTo',
};

// Non-configurable ledger fields that should not be rendered as snapshot rows.
const SNAPSHOT_SKIP = new Set(['id', 'policy', 'created_at', 'updated_at', 'created_by', 'latest_version', 'version_count']);

function statusChipColor(status) {
  if (status === 'draft') return 'warning';
  if (status === 'active') return 'success';
  return 'default';
}

function DetailField({ label, value }) {
  return (
    <Box sx={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      gap: 2, py: 0.75, borderBottom: '1px solid', borderColor: 'divider',
    }}>
      <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.04em', width: 180, flexShrink: 0, pt: 0.25 }}>
        {label}
      </Typography>
      <Typography sx={{ ...FONT.body, color: 'text.primary', textAlign: 'right', wordBreak: 'break-word' }}>
        {value ?? '—'}
      </Typography>
    </Box>
  );
}

function BooleanChip({ value, t }) {
  return (
    <Chip
      size="small"
      variant="outlined"
      color={value ? 'success' : 'default'}
      label={value ? t('yes') : t('no')}
    />
  );
}

export default function PolicyDetailPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { policyId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  useDocumentTitle(t('policyDetailsTitle'));

  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [tabIndex, setTabIndex] = useState(() => {
    const n = parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10);
    return Number.isFinite(n) && n < TAB_KEYS.length ? n : 0;
  });
  const handleTabChange = (_, v) => { setTabIndex(v); localStorage.setItem(STORAGE_KEY, String(v)); };

  const [propYear, setPropYear] = useState(String(new Date().getFullYear()));
  const [preview, setPreview] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [propagating, setPropagating] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const [versions, setVersions] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState(null);
  const [snapshotVersion, setSnapshotVersion] = useState(null);
  const [forkOpen, setForkOpen] = useState(false);
  const [changeSummary, setChangeSummary] = useState('');
  const [effectiveFrom, setEffectiveFrom] = useState('');
  const [forking, setForking] = useState(false);

  const loadData = useCallback(async () => {
    if (!policyId || !token) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchLeavePolicy(policyId, token);
      setPolicy(data);
    } catch (err) {
      setError(err?.message || t('policyLoadError'));
    } finally {
      setLoading(false);
    }
  }, [policyId, token, t]);

  useEffect(() => { loadData(); }, [loadData]);

  const loadVersions = useCallback(async () => {
    if (!policyId || !token) return;
    setVersionsLoading(true);
    setVersionsError(null);
    try {
      const data = await fetchLeavePolicyVersions(policyId, token);
      setVersions(Array.isArray(data) ? data : (data?.results ?? []));
    } catch (err) {
      setVersionsError(err?.message || t('policyVersionLoadError'));
    } finally {
      setVersionsLoading(false);
    }
  }, [policyId, token, t]);

  useEffect(() => {
    if (TAB_KEYS[tabIndex] === 'Versions') loadVersions();
  }, [tabIndex, loadVersions]);

  const resolveYear = () => parseInt(propYear, 10) || new Date().getFullYear();

  const handlePreview = async () => {
    setPropagating(true);
    try {
      const result = await propagateLeavePolicy(policyId, { year: resolveYear(), dry_run: true }, token);
      setPreview(result);
      setPreviewOpen(true);
    } catch (err) {
      setSnackbar({ open: true, message: err?.message || err?.feedback?.title || err?.detail || t('actionError'), severity: 'error' });
    } finally {
      setPropagating(false);
    }
  };

  const handleConfirmPropagate = async () => {
    setPropagating(true);
    try {
      await propagateLeavePolicy(policyId, { year: resolveYear(), dry_run: false }, token);
      setPreviewOpen(false);
      setPreview(null);
      setSnackbar({ open: true, message: t('policyPropagated'), severity: 'success' });
      await loadData();
    } catch (err) {
      setSnackbar({ open: true, message: err?.message || err?.feedback?.title || err?.detail || t('actionError'), severity: 'error' });
    } finally {
      setPropagating(false);
    }
  };

  const handleFork = async () => {
    setForking(true);
    try {
      const payload = {};
      if (changeSummary.trim()) payload.change_summary = changeSummary.trim();
      if (effectiveFrom) payload.effective_from = effectiveFrom;
      await forkLeavePolicy(policyId, payload, token);
      setForkOpen(false);
      setChangeSummary('');
      setEffectiveFrom('');
      setSnackbar({ open: true, message: t('policyVersionCreated'), severity: 'success' });
      await loadVersions();
      await loadData();
    } catch (err) {
      setSnackbar({ open: true, message: err?.message || err?.feedback?.title || err?.detail || t('actionError'), severity: 'error' });
    } finally {
      setForking(false);
    }
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={PolicyIcon} title={t('policyDetailsTitle')} />
        <LoadingSkeleton variant="table" />
      </PageContainer>
    );
  }

  if (error || !policy) {
    return (
      <PageContainer>
        <ErrorAlert message={error || t('policyLoadError')} onRetry={loadData} />
        <Button size="small" startIcon={<ArrowBackIcon />} onClick={() => navigate('/people/policies')} sx={{ mt: 1 }}>
          {tCommon('back')}
        </Button>
      </PageContainer>
    );
  }

  const statusLabel = policy.status ? t(`status${policy.status.charAt(0).toUpperCase()}${policy.status.slice(1)}`) : '—';
  const orgUnitsLabel = Array.isArray(policy.applies_to_org_units) && policy.applies_to_org_units.length
    ? policy.applies_to_org_units.join(', ')
    : '—';
  const contractTypesLabel = Array.isArray(policy.applies_to_contract_types) && policy.applies_to_contract_types.length
    ? policy.applies_to_contract_types.join(', ')
    : '—';

  const generalTab = (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <DetailField label={t('colName')} value={policy.name} />
      <DetailField label={t('colDescription')} value={policy.description} />
      <DetailField label={t('colLeaveType')} value={policy.leave_type_label || policy.leave_type} />
      <DetailField label={t('colStatus')} value={<Chip size="small" color={statusChipColor(policy.status)} label={statusLabel} />} />
      <DetailField label={t('colEffectiveFrom')} value={formatDate(policy.effective_from)} />
      <DetailField label={t('colEffectiveTo')} value={formatDate(policy.effective_to)} />
      <DetailField label={t('colUpdatedAt')} value={formatDate(policy.updated_at)} />
    </Paper>
  );

  const entitlementTab = (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <DetailField label={t('colDefaultDays')} value={policy.default_entitled_days ?? 0} />
      <DetailField
        label={t('colAccrual')}
        value={policy.accrual_method ? t(policy.accrual_method === 'monthly' ? 'accrualMonthly' : 'accrualUpfront') : '—'}
      />
    </Paper>
  );

  const carryoverTab = (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <DetailField label={t('colMaxCarryover')} value={policy.max_carryover_days ?? 0} />
      <DetailField label={t('colCarryoverAllowed')} value={<BooleanChip value={policy.is_carryover_allowed} t={t} />} />
    </Paper>
  );

  const eligibilityTab = (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <DetailField
        label={t('colGender')}
        value={policy.gender_restriction ? t(policy.gender_restriction === 'any' ? 'genderAny' : policy.gender_restriction === 'male' ? 'genderMale' : 'genderFemale') : '—'}
      />
      <DetailField label={t('colMinService')} value={policy.min_service_days ?? 0} />
      <DetailField label={t('colAppliesToOrgUnits')} value={orgUnitsLabel} />
      <DetailField label={t('colAppliesToContractTypes')} value={contractTypesLabel} />
    </Paper>
  );

  const workflowTab = (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <DetailField label={t('colRequiresApproval')} value={<BooleanChip value={policy.requires_approval} t={t} />} />
      <DetailField label={t('colNotes')} value={policy.notes} />
    </Paper>
  );

  const employeesTab = (
    <Stack spacing={2}>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <DetailField label={t('colEmployeeCount')} value={policy.employee_count ?? 0} />
      </Paper>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography sx={{ ...FONT.cardTitle, mb: 0.5 }}>{t('policyPropagate')}</Typography>
        <Typography sx={{ ...FONT.body, color: 'text.secondary', mb: 1.5 }}>{t('policyPropagateHint')}</Typography>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
          <TextField
            size="small"
            label={t('policyPropagateYear')}
            type="number"
            value={propYear}
            onChange={(e) => setPropYear(e.target.value)}
            slotProps={{ htmlInput: { min: '2000', max: '2100' } }}
            sx={{ width: 120 }}
          />
          <Button variant="contained" size="small" startIcon={<PublishIcon />} onClick={handlePreview} disabled={propagating}>
            {t('policyPropagate')}
          </Button>
        </Stack>
      </Paper>
    </Stack>
  );

  const renderSnapshotField = (key, value) => {
    const label = SNAPSHOT_LABELS[key] ? t(SNAPSHOT_LABELS[key]) : key;
    let display;
    if (Array.isArray(value)) {
      display = value.length ? value.join(', ') : t('policySnapshotAll');
    } else if (typeof value === 'boolean') {
      display = value ? t('yes') : t('no');
    } else if (key === 'accrual_method') {
      display = value === 'monthly' ? t('accrualMonthly') : value === 'upfront' ? t('accrualUpfront') : (value ?? '—');
    } else if (key === 'status' && value) {
      display = t(`status${value.charAt(0).toUpperCase()}${value.slice(1)}`);
    } else if (key === 'effective_from' || key === 'effective_to') {
      display = formatDate(value);
    } else {
      display = value == null || value === '' ? '—' : String(value);
    }
    return <DetailField key={key} label={label} value={display} />;
  };

  const versionsTab = (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
        <Typography sx={{ ...FONT.cardTitle }}>{t('policyVersionHistory')}</Typography>
        <Button size="small" variant="contained" disableElevation startIcon={<AddIcon />} onClick={() => setForkOpen(true)}>
          {t('policyNewVersion')}
        </Button>
      </Stack>

      {versionsLoading ? (
        <LoadingSkeleton variant="table" />
      ) : versionsError ? (
        <ErrorAlert message={versionsError} onRetry={loadVersions} />
      ) : versions.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, textAlign: 'center' }}>
          <Typography sx={{ ...FONT.cardTitle }}>{t('policyVersionsEmpty')}</Typography>
          <Typography sx={{ ...FONT.body, color: 'text.secondary', mt: 0.5 }}>{t('policyVersionsEmptyDesc')}</Typography>
        </Paper>
      ) : (
        <Stack spacing={1.5}>
          {versions.map((v) => (
            <Paper key={v.id} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Chip size="small" variant="outlined" color={v.effective_to == null ? 'primary' : 'default'} label={`V${v.version_number}`} />
                  {v.effective_to == null && (
                    <Chip size="small" variant="outlined" color="success" label={t('policyVersionCurrent')} />
                  )}
                </Stack>
                <Button size="small" onClick={() => setSnapshotVersion(v)}>{t('policyVersionDetails')}</Button>
              </Stack>
              <Box sx={{ mt: 1 }}>
                <DetailField label={t('colEffectiveFrom')} value={formatDate(v.effective_from)} />
                <DetailField label={t('colEffectiveTo')} value={v.effective_to ? formatDate(v.effective_to) : '—'} />
                <DetailField label={t('colChangeSummary')} value={v.change_summary} />
                <DetailField label={t('colCreatedBy')} value={v.created_by ?? '—'} />
                <DetailField label={t('colCreatedAt')} value={formatDate(v.created_at)} />
              </Box>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  );

  const tabPanels = [generalTab, entitlementTab, carryoverTab, eligibilityTab, workflowTab, employeesTab, versionsTab];

  return (
    <PageContainer>
      <PageHeader
        icon={PolicyIcon}
        title={policy.name || t('policyDetailsTitle')}
        subtitle={policy.leave_type_label || policy.leave_type || ''}
        badge={{ label: statusLabel, color: statusChipColor(policy.status) }}
        actions={
          <Button size="small" startIcon={<ArrowBackIcon />} onClick={() => navigate('/people/policies')}>
            {tCommon('back')}
          </Button>
        }
      />

      <Tabs value={tabIndex} onChange={handleTabChange} variant="scrollable" scrollButtons="auto" sx={{ mb: 1.5, borderBottom: 1, borderColor: 'divider' }}>
        {TAB_KEYS.map((k, i) => (
          <Tab
            key={k}
            label={t(`policyTab${k}`)}
            sx={{ fontWeight: tabIndex === i ? 600 : 400 }}
          />
        ))}
      </Tabs>

      {tabPanels[tabIndex]}

      <Dialog open={forkOpen} onClose={() => setForkOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{t('policyNewVersion')}</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ mt: 0.5 }}>
            <TextField
              size="small"
              fullWidth
              multiline
              minRows={3}
              label={t('colChangeSummary')}
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
            />
            <TextField
              size="small"
              fullWidth
              type="date"
              label={t('colEffectiveFrom')}
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setForkOpen(false)}>{t('cancel')}</Button>
          <Button variant="contained" disableElevation onClick={handleFork} disabled={forking}>
            {forking ? t('saving') : t('save')}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!snapshotVersion} onClose={() => setSnapshotVersion(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('policyVersionSnapshot')}</DialogTitle>
        <DialogContent>
          {snapshotVersion && (
            <Stack spacing={0.25}>
              <DetailField label={t('colVersion')} value={snapshotVersion.version_number} />
              {Object.entries(snapshotVersion.snapshot || {})
                .filter(([k]) => !SNAPSHOT_SKIP.has(k))
                .map(([k, v]) => renderSnapshotField(k, v))}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSnapshotVersion(null)}>{t('cancel')}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={previewOpen} onClose={() => setPreviewOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{t('policyPropagatePreview')}</DialogTitle>
        <DialogContent>
          {preview && (
            <Stack spacing={0.5}>
              <DetailField label={t('policyPropagateYear')} value={preview.year ?? resolveYear()} />
              <DetailField label={t('policyPropagateEligible')} value={preview.eligible ?? 0} />
              <DetailField label={t('policyPropagateWillCreate')} value={preview.will_create ?? 0} />
              <DetailField label={t('policyPropagateWillUpdate')} value={preview.will_update ?? 0} />
              <DetailField label={t('policyPropagateSkipped')} value={preview.skipped ?? 0} />
              {(preview.eligible ?? 0) === 0 && (
                <Typography sx={{ ...FONT.body, color: 'text.secondary', pt: 0.5 }}>{t('policyPropagateEmpty')}</Typography>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreviewOpen(false)}>{t('cancel')}</Button>
          <Button
            variant="contained"
            disableElevation
            onClick={handleConfirmPropagate}
            disabled={propagating || !preview || (preview.eligible ?? 0) === 0}
          >
            {propagating ? t('saving') : t('policyPropagateConfirm')}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </PageContainer>
  );
}
