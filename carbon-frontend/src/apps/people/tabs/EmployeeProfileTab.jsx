// src/apps/people/tabs/EmployeeProfileTab.jsx
// Employee 360 — "Profile" tab, sectioned accordion with inline CRUD.
//
// Methodology (sectioned, audited PATCH):
//   - Each accordion maps to a coherent field group on Employee (Identity /
//     Employment / Organisation / Compensation).
//   - Collapsed = a compact summary of key values.
//   - Expanded = read-only field grid + a per-section "Edit" affordance.
//   - Edit = a local draft seeded from the entity; Save PATCHes ONLY that
//     section's fields (no full-object overwrite, no accidental nulling of
//     untouched fields) then calls onSaved() to reload the 360.
//   - Compensation is Tier-2: server-masked for viewers without
//     people:view_compensation; reveal is on-demand and audited.
//   - Lifecycle ops (deactivate/reactivate) live in the page header, NOT here
//     and NOT in the grid.
//
// Read-only context strips (lifecycle + required interventions) remain at the
// top for the compliance/at-a-glance view.

import React, { useEffect, useMemo, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Autocomplete, Box, Button,
  Grid, MenuItem, Stack, TextField, Tooltip, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import EditIcon from '@mui/icons-material/Edit';
import LockIcon from '@mui/icons-material/Lock';
import BadgeIcon from '@mui/icons-material/Badge';
import WorkIcon from '@mui/icons-material/Work';
import BusinessIcon from '@mui/icons-material/Business';
import PaidIcon from '@mui/icons-material/Paid';
import FlagIcon from '@mui/icons-material/Flag';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import WorkHistoryIcon from '@mui/icons-material/WorkHistory';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import PersonOffIcon from '@mui/icons-material/PersonOff';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import EditNoteIcon from '@mui/icons-material/EditNote';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { useReferenceOptions } from '../../../hooks/useReferenceOptions';
import { useCompensationAccess } from '../useCompensationAccess';
import { updateEmployee, fetchCompensationLedger } from '../../../api/people';
import EmployeePicker from '../EmployeePicker';
import { daysUntilExpiry, expiryUrgency, formatAmount, formatDate, refCode, refLabel } from '../utils';
import {
  fetchOrgUnits,
  orgUnitDepth,
  orgUnitOptionLabel,
  prepareOrgUnitsForPicker,
} from '../../../api/orgUnits';

// ── Event kind config (mirrors EmployeeTimelineTab) ────────────────────
const EV_CFG = {
  hired:            { Icon: WorkHistoryIcon,  color: 'success', label: 'Joined' },
  transferred:      { Icon: SwapHorizIcon,    color: 'primary', label: 'Transferred' },
  promoted:         { Icon: TrendingUpIcon,   color: 'info',    label: 'Promoted' },
  salary_change:    { Icon: PaidIcon,         color: 'warning', label: 'Salary Changed' },
  grade_change:     { Icon: TrendingUpIcon,   color: 'info',    label: 'Grade Changed' },
  contract_renewed: { Icon: AssignmentIcon,   color: 'info',    label: 'Contract Renewed' },
  rotation_changed: { Icon: AutorenewIcon,    color: 'default', label: 'Rotation Changed' },
  deactivated:      { Icon: PersonOffIcon,    color: 'error',   label: 'Deactivated' },
  reactivated:      { Icon: PersonAddIcon,    color: 'success', label: 'Reactivated' },
  profile_updated:  { Icon: EditNoteIcon,     color: 'default', label: 'Profile Updated' },
};
const DEF_CFG = { Icon: EditNoteIcon, color: 'default', label: null };

// ── Lifecycle Strip ──────────────────────────────────────────────────────
function LifecycleStrip({ joinDate, timelineEvents }) {
  const milestones = useMemo(() => {
    if (!joinDate) return [];
    const today = new Date();
    const joined = new Date(joinDate);

    const list = [{ date: joined, kind: 'hired', label: 'Joined', color: 'success' }];

    // Kuwait Labour Law: 6-month probation standard
    const probEnd = new Date(joined);
    probEnd.setMonth(probEnd.getMonth() + 6);
    if (probEnd < today) {
      list.push({ date: probEnd, kind: 'probation', label: 'Probation End', color: 'primary' });
    }

    // Key events from timeline (exclude profile_updated noise)
    const KEY_KINDS = new Set(['transferred', 'promoted', 'salary_change', 'contract_renewed', 'grade_change']);
    for (const ev of (timelineEvents || [])) {
      if (KEY_KINDS.has(ev.event_kind) && ev.effective_date) {
        const cfg = EV_CFG[ev.event_kind] || DEF_CFG;
        list.push({
          date: new Date(ev.effective_date),
          kind: ev.event_kind,
          label: cfg.label || ev.event_kind,
          color: cfg.color,
          event: ev,
        });
      }
    }

    list.push({ date: today, kind: 'today', label: 'Today', isToday: true, color: 'primary' });
    return list.sort((a, b) => a.date - b.date);
  }, [joinDate, timelineEvents]);

  if (milestones.length < 2) return null;

  const minMs = milestones[0].date.getTime();
  const maxMs = milestones[milestones.length - 1].date.getTime();
  const span = maxMs - minMs || 1;
  const pct = (ms) => ((ms - minMs) / span) * 100;

  return (
    <Box sx={{
      border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 1.5, mb: 1.5, bgcolor: 'background.paper',
    }}>
      <Typography sx={{ fontSize: '0.625rem', fontWeight: 700, color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em', mb: 1.5 }}>
        Lifecycle
      </Typography>
      <Box sx={{ position: 'relative', height: 44, mx: 1 }}>
        <Box sx={{ position: 'absolute', top: '36%', left: 0, right: 0, height: 2, bgcolor: 'divider' }} />
        {milestones.map((m, i) => {
          const left = `${pct(m.date.getTime())}%`;
          const dotColor = m.isToday ? 'primary.main' : m.color === 'default' ? 'text.disabled' : `${m.color}.main`;
          return (
            <Tooltip
              key={i}
              title={`${m.label} · ${m.isToday ? 'Today' : formatDate(m.date.toISOString())}`}
              placement="top"
              arrow
            >
              <Box sx={{ position: 'absolute', left, top: '50%', transform: 'translate(-50%, -50%)', cursor: 'pointer' }}>
                <Box sx={{
                  width: m.isToday ? 13 : 9, height: m.isToday ? 13 : 9,
                  borderRadius: '50%',
                  bgcolor: dotColor,
                  border: m.isToday ? '2.5px solid white' : 'none',
                  boxShadow: m.isToday ? `0 0 0 2.5px ${dotColor}` : 'none',
                  transition: 'transform 0.15s',
                  '&:hover': { transform: 'scale(1.35)' },
                }} />
                <Typography sx={{
                  position: 'absolute', top: 14, left: '50%', transform: 'translateX(-50%)',
                  fontSize: '0.5rem', color: m.isToday ? 'primary.main' : 'text.disabled',
                  fontWeight: m.isToday ? 700 : 400, whiteSpace: 'nowrap',
                }}>
                  {m.isToday ? 'Now' : m.date.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' })}
                </Typography>
              </Box>
            </Tooltip>
          );
        })}
      </Box>
    </Box>
  );
}

// ── Required Interventions ───────────────────────────────────────────────
function buildInterventions(emp, certifications, leaveEntitlements) {
  const list = [];
  const currentYear = new Date().getFullYear();
  const id = emp.empId ?? emp.id;

  const myCerts = certifications.filter((c) => c.employee === id);
  for (const cert of myCerts) {
    const certName = refLabel(cert.cert_type) || refCode(cert.cert_type) || 'Certification';
    const u = expiryUrgency(cert.expiry_date);
    if (u === 'expired') {
      list.push({ severity: 'error', message: `${certName} expired ${Math.abs(daysUntilExpiry(cert.expiry_date))} days ago`, icon: ErrorOutlineIcon });
    } else if (u === 'critical' || u === 'warning') {
      list.push({ severity: 'warning', message: `${certName} expiring in ${daysUntilExpiry(cert.expiry_date)} days`, icon: WarningAmberIcon });
    }
  }

  if (!emp.civil_id) {
    list.push({ severity: 'info', message: 'Civil ID not on file — required for KOC compliance', icon: InfoOutlinedIcon });
  }
  if (!emp.name_ar_given && !emp.name_ar_family) {
    list.push({ severity: 'info', message: 'Arabic name required for payroll records', icon: InfoOutlinedIcon });
  }

  const myEnts = leaveEntitlements.filter((e) => e.employee === id && e.year === currentYear);
  for (const ent of myEnts) {
    if (Number(ent.used_days) > Number(ent.entitled_days)) {
      const over = (Number(ent.used_days) - Number(ent.entitled_days)).toFixed(1);
      list.push({ severity: 'warning', message: `${ent.leave_type} overrun by ${over} days`, icon: WarningAmberIcon });
    }
  }

  return list;
}

function InterventionRow({ severity, message, icon: Icon }) {
  const colorMap = { error: 'error', warning: 'warning', info: 'info' };
  const c = colorMap[severity] || 'info';
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.875, py: 0.5, px: 0.875, borderRadius: 1, bgcolor: `${c}.50` }}>
      <Icon sx={{ fontSize: '0.875rem', color: `${c}.main`, flexShrink: 0 }} />
      <Typography sx={{ flex: 1, fontSize: '0.75rem', color: 'text.primary' }}>{message}</Typography>
    </Box>
  );
}

// ── Accordion section wrapper ────────────────────────────────────────────
function Section({ title, icon: Icon, summary, expanded, onToggle, children }) {
  return (
    <Accordion
      expanded={expanded}
      onChange={onToggle}
      variant="outlined"
      disableGutters
      sx={{ mb: 1, borderRadius: 2, bgcolor: 'background.paper', '&:before': { display: 'none' } }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 44, '& .MuiAccordionSummary-content': { my: 0 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0, flex: 1 }}>
          <Icon sx={{ fontSize: '1rem', color: 'primary.main', flexShrink: 0 }} />
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, flexShrink: 0 }}>{title}</Typography>
          {!expanded && summary ? (
            <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              · {summary}
            </Typography>
          ) : null}
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ borderTop: 1, borderColor: 'divider', p: 2, pt: 1.5 }}>{children}</AccordionDetails>
    </Accordion>
  );
}

// ── Read-only field ──────────────────────────────────────────────────────
function ReadField({ label, value }) {
  return (
    <Box>
      <Typography sx={{ fontSize: '0.5625rem', color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, wordBreak: 'break-word' }}>{value || '—'}</Typography>
    </Box>
  );
}

function SectionHeading({ icon: Icon, title }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.75 }}>
      <Icon sx={{ fontSize: '1rem', color: 'primary.main' }} />
      <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'text.secondary' }}>
        {title}
      </Typography>
    </Box>
  );
}

// ── Section action row (Edit ↔ Save/Cancel) ──────────────────────────────
function SectionActions({ editing, onEdit, onSave, onCancel, saving }) {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  if (editing) {
    return (
      <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
        <Button size="small" variant="contained" onClick={onSave} disabled={saving}>
          {tCommon('save')}
        </Button>
        <Button size="small" onClick={onCancel} disabled={saving}>
          {tCommon('cancel')}
        </Button>
      </Box>
    );
  }
  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
      <Button size="small" startIcon={<EditIcon sx={{ fontSize: '1rem' }} />} onClick={onEdit}>
        {t('editSection')}
      </Button>
    </Box>
  );
}

// ── Governed reference Autocomplete (code stored in draft) ────────────────
function RefAutocomplete({ label, value, onChange, options }) {
  const selected = options.find((o) => o.value === value) || null;
  return (
    <Autocomplete
      size="small"
      fullWidth
      options={options}
      value={selected}
      onChange={(e, v) => onChange(v ? v.value : '')}
      getOptionLabel={(o) => o.label}
      isOptionEqualToValue={(a, b) => a.value === b.value}
      renderInput={(params) => <TextField {...params} label={label} />}
    />
  );
}

// ── Main Component ────────────────────────────────────────────────────────
export default function EmployeeProfileTab({ entityData, additionalProps }) {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { token } = useAuth();
  const { notify } = useNotification();
  const { canViewCompensation } = useCompensationAccess();
  const emp = entityData || {};

  const nationalityRef = useReferenceOptions('nationality');
  const genderRef = useReferenceOptions('gender');
  const employmentTypeRef = useReferenceOptions('employment_type');
  const contractTypeRef = useReferenceOptions('contract_type');
  const rotationRef = useReferenceOptions('rotation_pattern');

  const [expanded, setExpanded] = useState({ identity: true, employment: true });
  const [editing, setEditing] = useState(null); // section key currently in edit mode
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [revealedSalary, setRevealedSalary] = useState(null);

  // One-shot "edit all sections" mode (driven by the detail-page hero button).
  const editAll = Boolean(additionalProps?.editAll);
  const onEditAllChange = additionalProps?.onEditAllChange;
  const [editAllDraft, setEditAllDraft] = useState({});

  const seedAllDraft = () => {
    const d = {};
    const textFields = [
      'name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family', 'civil_id',
      'position', 'org_unit', 'manager',
    ];
    for (const f of textFields) d[f] = emp[f] ?? '';
    d.gender = refCode(emp.gender);
    d.nationality = refCode(emp.nationality);
    d.employment_type = refCode(emp.employment_type);
    d.contract_type = refCode(emp.contract_type);
    d.rotation = refCode(emp.rotation);
    d.date_of_birth = emp.date_of_birth ? String(emp.date_of_birth).slice(0, 10) : '';
    d.join_date = emp.join_date ? String(emp.join_date).slice(0, 10) : '';
    d.kuwaitization = Boolean(emp.kuwaitization);
    return d;
  };

  useEffect(() => {
    if (editAll) setEditAllDraft(seedAllDraft());
    else setEditing(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editAll]);

  const toggle = (key) => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const interventions = useMemo(
    () => buildInterventions(emp, emp.certifications || [], emp.leaveEntitlements || []),
    [emp],
  );

  const positions = Array.isArray(emp.positions) ? emp.positions : [];
  const [orgCatalog, setOrgCatalog] = useState(null);
  const editingOrg = editAll || editing === 'organization';
  useEffect(() => {
    if (!editingOrg || orgCatalog || !token) return undefined;
    let cancelled = false;
    fetchOrgUnits(token)
      .then((rows) => { if (!cancelled) setOrgCatalog(Array.isArray(rows) ? rows : []); })
      .catch(() => { if (!cancelled) setOrgCatalog([]); });
    return () => { cancelled = true; };
  }, [editingOrg, orgCatalog, token]);
  const orgUnitsForPicker = useMemo(() => {
    if (orgCatalog) return prepareOrgUnitsForPicker(orgCatalog);
    if (!emp.org_unit) return [];
    return prepareOrgUnitsForPicker([{
      id: emp.org_unit,
      name: emp.orgUnitName || String(emp.org_unit),
      parent: null,
    }]);
  }, [orgCatalog, emp.org_unit, emp.orgUnitName]);
  const orgUnitById = useMemo(() => {
    const map = new Map();
    for (const u of orgUnitsForPicker) map.set(u.id, u);
    return map;
  }, [orgUnitsForPicker]);
  const positionTitle = emp.position_title || positions.find((p) => p.id === emp.position)?.title || null;
  const managerLabel = emp.managerLabel || t('managerUnassigned');

  const identitySummary = [emp.civil_id, refLabel(emp.nationality) || refCode(emp.nationality)].filter(Boolean).join(' · ');
  const employmentSummary = [
    refLabel(emp.employment_type) || refCode(emp.employment_type),
    refLabel(emp.contract_type) || refCode(emp.contract_type),
    refLabel(emp.rotation) || refCode(emp.rotation),
    positionTitle,
  ].filter(Boolean).join(' · ');
  const orgSummary = [emp.orgUnitName, managerLabel].filter(Boolean).join(' · ');
  const compSummary = canViewCompensation
    ? (emp.basic_salary != null ? formatAmount(emp.basic_salary) : '')
    : t('restrictedLabel');

  const startEdit = (key) => {
    if (key === 'employment') additionalProps?.loadPositions?.();
    const fieldsBySection = {
      identity: ['name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family', 'gender', 'civil_id', 'date_of_birth', 'nationality'],
      employment: ['employment_type', 'contract_type', 'join_date', 'rotation', 'kuwaitization', 'position'],
      organization: ['org_unit', 'manager'],
      // NSR-2B: compensation is ledger-driven — no inline edit of basic_salary.
    };
    const governed = new Set(['gender', 'nationality', 'employment_type', 'contract_type', 'rotation']);
    const d = {};
    for (const f of fieldsBySection[key] || []) {
      const v = emp[f];
      if ((f === 'date_of_birth' || f === 'join_date') && v) d[f] = String(v).slice(0, 10);
      else if (governed.has(f)) d[f] = refCode(v);
      else d[f] = v ?? '';
    }
    setDraft(d);
    setEditing(key);
  };

  const cancelEdit = () => {
    setEditing(null);
    setDraft({});
  };

  const handleChange = (e) => {
    const { name, value, checked, type } = e.target;
    setDraft((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const setDraftField = (name, value) => setDraft((prev) => ({ ...prev, [name]: value }));
  const setEditAllField = (name, value) => setEditAllDraft((prev) => ({ ...prev, [name]: value }));

  const buildPayloadFrom = (source, key) => {
    const p = {};
    const putCode = (f) => {
      const code = String(source[f] ?? '').trim();
      if (code) p[f] = code;
    };
    if (key === 'identity') {
      for (const f of ['name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family', 'civil_id']) {
        p[f] = String(source[f] ?? '').trim();
      }
      putCode('gender');
      putCode('nationality');
      p.date_of_birth = source.date_of_birth || null;
    } else if (key === 'employment') {
      putCode('employment_type');
      putCode('contract_type');
      putCode('rotation');
      p.join_date = source.join_date || null;
      p.kuwaitization = Boolean(source.kuwaitization);
      p.position = source.position ? Number(source.position) : null;
    } else if (key === 'organization') {
      p.org_unit = source.org_unit ? Number(source.org_unit) : null;
      p.manager = source.manager ? Number(source.manager) : null;
    }
    return p;
  };

  const save = async (key) => {
    setSaving(true);
    try {
      await updateEmployee(emp.id, buildPayloadFrom(draft, key), token);
      notify({ message: t('profileSaved'), type: 'success' });
      setEditing(null);
      setDraft({});
      additionalProps?.onSaved?.();
    } catch (err) {
      notify({
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        type: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleEditAllChange = (e) => {
    const { name, value, checked, type } = e.target;
    setEditAllDraft((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const cancelAll = () => onEditAllChange?.(false);

  const saveAll = async () => {
    setSaving(true);
    try {
      const payload = {};
      for (const key of ['identity', 'employment', 'organization']) {
        Object.assign(payload, buildPayloadFrom(editAllDraft, key));
      }
      // NSR-2B: never PATCH basic_salary from profile — use Pay tab ledger append.
      await updateEmployee(emp.id, payload, token);
      notify({ message: t('profileSaved'), type: 'success' });
      onEditAllChange?.(false);
      additionalProps?.onSaved?.();
    } catch (err) {
      notify({
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        type: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  const reveal = async () => {
    try {
      const res = await fetchCompensationLedger(emp.id, token);
      setRevealedSalary(res?.basic_salary ?? null);
    } catch {
      notify({ message: t('revealFailed'), type: 'error' });
    }
  };

  return (
    <Box sx={{ p: 2 }}>
      {editAll ? (
        <Stack spacing={1.5}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography sx={{ fontSize: '0.875rem', fontWeight: 700 }}>{t('profileEditTitle')}</Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button size="small" variant="contained" onClick={saveAll} disabled={saving}>{tCommon('save')}</Button>
              <Button size="small" onClick={cancelAll} disabled={saving}>{tCommon('cancel')}</Button>
            </Box>
          </Box>

          <SectionHeading icon={BadgeIcon} title={t('sectionIdentity')} />
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" label={t('formNameEnGiven')} name="name_en_given" value={editAllDraft.name_en_given ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" label={t('formNameEnFamily')} name="name_en_family" value={editAllDraft.name_en_family ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" label={t('formNameArGiven')} name="name_ar_given" value={editAllDraft.name_ar_given ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" label={t('formNameArFamily')} name="name_ar_family" value={editAllDraft.name_ar_family ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <RefAutocomplete
                label={t('formGender')}
                value={editAllDraft.gender ?? ''}
                onChange={(v) => setEditAllField('gender', v)}
                options={genderRef.options}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" label={t('formCivilId')} name="civil_id" value={editAllDraft.civil_id ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" type="date" slotProps={{ inputLabel: { shrink: true } }} label={t('formDateOfBirth')} name="date_of_birth" value={editAllDraft.date_of_birth ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <RefAutocomplete
                label={t('formNationality')}
                value={editAllDraft.nationality ?? ''}
                onChange={(v) => setEditAllField('nationality', v)}
                options={nationalityRef.options}
              />
            </Grid>
          </Grid>

          <SectionHeading icon={WorkIcon} title={t('sectionEmployment')} />
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <RefAutocomplete
                label={t('formEmploymentType')}
                value={editAllDraft.employment_type ?? ''}
                onChange={(v) => setEditAllField('employment_type', v)}
                options={employmentTypeRef.options}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <RefAutocomplete
                label={t('formContractType')}
                value={editAllDraft.contract_type ?? ''}
                onChange={(v) => setEditAllField('contract_type', v)}
                options={contractTypeRef.options}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" type="date" slotProps={{ inputLabel: { shrink: true } }} label={t('formJoinDate')} name="join_date" value={editAllDraft.join_date ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <RefAutocomplete
                label={t('formRotation')}
                value={editAllDraft.rotation ?? ''}
                onChange={(v) => setEditAllField('rotation', v)}
                options={rotationRef.options}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" select label={t('colPosition')} name="position" value={editAllDraft.position ?? ''} onChange={handleEditAllChange}>
                <MenuItem value="">{t('managerUnassigned')}</MenuItem>
                {positions.map((p) => (
                  <MenuItem key={p.id} value={p.id}>{p.title || p.code}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" select label={t('formKuwaitization')} name="kuwaitization" value={editAllDraft.kuwaitization ? 'true' : 'false'} onChange={(e) => setEditAllDraft((prev) => ({ ...prev, kuwaitization: e.target.value === 'true' }))}>
                <MenuItem value="true">{t('yes')}</MenuItem>
                <MenuItem value="false">{t('no')}</MenuItem>
              </TextField>
            </Grid>
          </Grid>

          <SectionHeading icon={BusinessIcon} title={t('sectionOrganization')} />
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField fullWidth size="small" select label={t('formOrgUnit')} name="org_unit" value={editAllDraft.org_unit ?? ''} onChange={handleEditAllChange}>
                <MenuItem value="">{t('managerUnassigned')}</MenuItem>
                {orgUnitsForPicker.map((u) => (
                  <MenuItem key={u.id} value={u.id}>
                    {orgUnitOptionLabel(u, { depth: orgUnitDepth(u, orgUnitById) })}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <EmployeePicker
                token={token}
                label={t('formManager')}
                value={editAllDraft.manager ?? ''}
                initialLabel={emp.manager_label || emp.managerLabel}
                excludeId={emp.id}
                onChange={(id) => setEditAllField('manager', id || '')}
              />
            </Grid>
          </Grid>

          {canViewCompensation && (
            <>
              <SectionHeading icon={PaidIcon} title={t('sectionCompensation')} />
              <Alert severity="info" role="status" sx={{ mb: 1 }}>
                {t('compPayViaLedger')}
              </Alert>
              <Grid container spacing={1.5}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    fullWidth
                    size="small"
                    label={t('formBasicSalaryReadonly')}
                    value={emp.basic_salary != null ? formatAmount(emp.basic_salary) : t('compBasicNone')}
                    disabled
                    helperText={t('formBasicSalaryLedgerHint')}
                    slotProps={{ htmlInput: { 'aria-readonly': true, readOnly: true } }}
                    data-testid="profile-basic-salary-readonly"
                  />
                </Grid>
              </Grid>
            </>
          )}
        </Stack>
      ) : (
        <>

      {/* ── Lifecycle (read-only) ── */}
      <LifecycleStrip joinDate={emp.join_date} timelineEvents={emp.timelineEvents} />

      {/* ── Required Interventions (read-only) ── */}
      {interventions.length > 0 && (
        <Section
          title={t('sectionInterventions')}
          icon={FlagIcon}
          summary={`${interventions.length}`}
          expanded={Boolean(expanded.interventions)}
          onToggle={() => toggle('interventions')}
        >
          <Stack spacing={0.5}>
            {interventions.map((iv, i) => <InterventionRow key={i} {...iv} />)}
          </Stack>
        </Section>
      )}

      {/* ── Identity ── */}
      <Section
        title={t('sectionIdentity')}
        icon={BadgeIcon}
        summary={identitySummary}
        expanded={Boolean(expanded.identity)}
        onToggle={() => toggle('identity')}
      >
        {editing === 'identity' ? (
          <Stack spacing={1.5}>
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" label={t('formNameEnGiven')} name="name_en_given" value={draft.name_en_given ?? ''} onChange={handleChange} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" label={t('formNameEnFamily')} name="name_en_family" value={draft.name_en_family ?? ''} onChange={handleChange} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" label={t('formNameArGiven')} name="name_ar_given" value={draft.name_ar_given ?? ''} onChange={handleChange} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" label={t('formNameArFamily')} name="name_ar_family" value={draft.name_ar_family ?? ''} onChange={handleChange} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <RefAutocomplete
                  label={t('formGender')}
                  value={draft.gender ?? ''}
                  onChange={(v) => setDraftField('gender', v)}
                  options={genderRef.options}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" label={t('formCivilId')} name="civil_id" value={draft.civil_id ?? ''} onChange={handleChange} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" type="date" slotProps={{ inputLabel: { shrink: true } }} label={t('formDateOfBirth')} name="date_of_birth" value={draft.date_of_birth ?? ''} onChange={handleChange} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <RefAutocomplete
                  label={t('formNationality')}
                  value={draft.nationality ?? ''}
                  onChange={(v) => setDraftField('nationality', v)}
                  options={nationalityRef.options}
                />
              </Grid>
            </Grid>
            <SectionActions editing onSave={() => save('identity')} onCancel={cancelEdit} saving={saving} />
          </Stack>
        ) : (
          <Box>
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formNameEnGiven')} value={emp.name_en_given} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formNameEnFamily')} value={emp.name_en_family} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formNameArGiven')} value={emp.name_ar_given} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formNameArFamily')} value={emp.name_ar_family} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formGender')} value={refLabel(emp.gender) || refCode(emp.gender)} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formCivilId')} value={emp.civil_id} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formDateOfBirth')} value={formatDate(emp.date_of_birth)} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formNationality')} value={refLabel(emp.nationality) || refCode(emp.nationality)} /></Grid>
            </Grid>
            <SectionActions onEdit={() => startEdit('identity')} />
          </Box>
        )}
      </Section>

      {/* ── Employment ── */}
      <Section
        title={t('sectionEmployment')}
        icon={WorkIcon}
        summary={employmentSummary}
        expanded={Boolean(expanded.employment)}
        onToggle={() => toggle('employment')}
      >
        {editing === 'employment' ? (
          <Stack spacing={1.5}>
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <RefAutocomplete
                  label={t('formEmploymentType')}
                  value={draft.employment_type ?? ''}
                  onChange={(v) => setDraftField('employment_type', v)}
                  options={employmentTypeRef.options}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <RefAutocomplete
                  label={t('formContractType')}
                  value={draft.contract_type ?? ''}
                  onChange={(v) => setDraftField('contract_type', v)}
                  options={contractTypeRef.options}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" type="date" slotProps={{ inputLabel: { shrink: true } }} label={t('formJoinDate')} name="join_date" value={draft.join_date ?? ''} onChange={handleChange} />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <RefAutocomplete
                  label={t('formRotation')}
                  value={draft.rotation ?? ''}
                  onChange={(v) => setDraftField('rotation', v)}
                  options={rotationRef.options}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" select label={t('colPosition')} name="position" value={draft.position ?? ''} onChange={handleChange}>
                  <MenuItem value="">{t('managerUnassigned')}</MenuItem>
                  {positions.map((p) => (
                    <MenuItem key={p.id} value={p.id}>{p.title || p.code}</MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField fullWidth size="small" select label={t('formKuwaitization')} name="kuwaitization" value={draft.kuwaitization ? 'true' : 'false'} onChange={(e) => setDraft((prev) => ({ ...prev, kuwaitization: e.target.value === 'true' }))}>
                  <MenuItem value="true">{t('yes')}</MenuItem>
                  <MenuItem value="false">{t('no')}</MenuItem>
                </TextField>
              </Grid>
            </Grid>
            <SectionActions editing onSave={() => save('employment')} onCancel={cancelEdit} saving={saving} />
          </Stack>
        ) : (
          <Box>
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('colEmployeeNo')} value={emp.employee_no} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formEmploymentType')} value={refLabel(emp.employment_type) || refCode(emp.employment_type)} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formContractType')} value={refLabel(emp.contract_type) || refCode(emp.contract_type)} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formJoinDate')} value={formatDate(emp.join_date)} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formRotation')} value={refLabel(emp.rotation) || refCode(emp.rotation)} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('colPosition')} value={positionTitle} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formKuwaitization')} value={emp.kuwaitization ? t('yes') : t('no')} /></Grid>
            </Grid>
            <SectionActions onEdit={() => startEdit('employment')} />
          </Box>
        )}
      </Section>

      {/* ── Organisation ── */}
      <Section
        title={t('sectionOrganization')}
        icon={BusinessIcon}
        summary={orgSummary}
        expanded={Boolean(expanded.organization)}
        onToggle={() => toggle('organization')}
      >
        {editing === 'organization' ? (
          <Stack spacing={1.5}>
            <TextField fullWidth size="small" select label={t('formOrgUnit')} name="org_unit" value={draft.org_unit ?? ''} onChange={handleChange}>
              <MenuItem value="">{t('managerUnassigned')}</MenuItem>
              {orgUnitsForPicker.map((u) => (
                <MenuItem key={u.id} value={u.id}>
                  {orgUnitOptionLabel(u, { depth: orgUnitDepth(u, orgUnitById) })}
                </MenuItem>
              ))}
            </TextField>
            <EmployeePicker
              token={token}
              label={t('formManager')}
              value={draft.manager ?? ''}
              initialLabel={emp.manager_label || emp.managerLabel}
              excludeId={emp.id}
              onChange={(id) => setDraft((prev) => ({ ...prev, manager: id || '' }))}
            />
            <SectionActions editing onSave={() => save('organization')} onCancel={cancelEdit} saving={saving} />
          </Stack>
        ) : (
          <Box>
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formOrgUnit')} value={emp.orgUnitName} /></Grid>
              <Grid size={{ xs: 6, sm: 4 }}><ReadField label={t('formManager')} value={managerLabel} /></Grid>
            </Grid>
            <SectionActions onEdit={() => startEdit('organization')} />
          </Box>
        )}
      </Section>

      {/* ── Compensation (Tier-2, read-only — ledger SoT via Pay tab) ── */}
      <Section
        title={t('sectionCompensation')}
        icon={PaidIcon}
        summary={compSummary}
        expanded={Boolean(expanded.compensation)}
        onToggle={() => toggle('compensation')}
      >
        {canViewCompensation ? (
          <Stack spacing={1.5} data-testid="profile-compensation-readonly">
            <Alert severity="info" role="status">
              {t('compPayViaLedger')}
            </Alert>
            <TextField
              fullWidth
              size="small"
              label={t('formBasicSalaryReadonly')}
              value={emp.basic_salary != null ? formatAmount(emp.basic_salary) : t('compBasicNone')}
              disabled
              helperText={t('formBasicSalaryLedgerHint')}
              slotProps={{ htmlInput: { 'aria-readonly': true, readOnly: true } }}
              data-testid="profile-basic-salary-readonly"
            />
          </Stack>
        ) : (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
            <Box>
              <Typography sx={{ fontSize: '0.5625rem', color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                {t('restrictedLabel')}
              </Typography>
              <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>
                {revealedSalary != null ? formatAmount(revealedSalary) : '••••••…'}
              </Typography>
            </Box>
            {revealedSalary != null ? (
              <Button size="small" onClick={() => setRevealedSalary(null)}>{t('hideAmount')}</Button>
            ) : (
              <Button size="small" startIcon={<LockIcon sx={{ fontSize: '1rem' }} />} onClick={reveal}>{t('revealAmount')}</Button>
            )}
          </Box>
        )}
      </Section>
        </>
      )}
    </Box>
  );
}
