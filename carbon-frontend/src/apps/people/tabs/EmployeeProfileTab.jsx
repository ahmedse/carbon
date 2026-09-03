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
  Accordion, AccordionDetails, AccordionSummary, Box, Button,
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
import { useCompensationAccess } from '../useCompensationAccess';
import { updateEmployee, fetchCompensationLedger } from '../../../api/people';
import { daysUntilExpiry, expiryUrgency, formatAmount, formatDate } from '../utils';

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
    const u = expiryUrgency(cert.expiry_date);
    if (u === 'expired') {
      list.push({ severity: 'error', message: `${cert.cert_type} expired ${Math.abs(daysUntilExpiry(cert.expiry_date))} days ago`, icon: ErrorOutlineIcon });
    } else if (u === 'critical' || u === 'warning') {
      list.push({ severity: 'warning', message: `${cert.cert_type} expiring in ${daysUntilExpiry(cert.expiry_date)} days`, icon: WarningAmberIcon });
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

// ── Main Component ────────────────────────────────────────────────────────
export default function EmployeeProfileTab({ entityData, additionalProps }) {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { token } = useAuth();
  const { notify } = useNotification();
  const { canViewCompensation } = useCompensationAccess();
  const emp = entityData || {};

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
      'name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family', 'gender', 'civil_id',
      'nationality', 'nationality_code', 'employment_type_code', 'contract_type_code', 'rotation',
      'position', 'org_unit', 'manager', 'basic_salary',
    ];
    for (const f of textFields) d[f] = emp[f] ?? '';
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
  const positionTitle = positions.find((p) => p.id === emp.position)?.title || null;
  const managerLabel = emp.managerLabel || t('managerUnassigned');

  const identitySummary = [emp.civil_id, emp.nationality_code || emp.nationality].filter(Boolean).join(' · ');
  const employmentSummary = [emp.employment_type_code, emp.contract_type_code, emp.rotation, positionTitle].filter(Boolean).join(' · ');
  const orgSummary = [emp.orgUnitName, managerLabel].filter(Boolean).join(' · ');
  const compSummary = canViewCompensation
    ? (emp.basic_salary != null ? formatAmount(emp.basic_salary) : '')
    : t('restrictedLabel');

  const startEdit = (key) => {
    const fieldsBySection = {
      identity: ['name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family', 'gender', 'civil_id', 'date_of_birth', 'nationality', 'nationality_code'],
      employment: ['employment_type_code', 'contract_type_code', 'join_date', 'rotation', 'kuwaitization', 'position'],
      organization: ['org_unit', 'manager'],
      compensation: ['basic_salary'],
    };
    const d = {};
    for (const f of fieldsBySection[key] || []) {
      const v = emp[f];
      if ((f === 'date_of_birth' || f === 'join_date') && v) d[f] = String(v).slice(0, 10);
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

  const buildPayloadFrom = (source, key) => {
    const p = {};
    if (key === 'identity') {
      for (const f of ['name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family', 'gender', 'civil_id', 'nationality', 'nationality_code']) {
        p[f] = String(source[f] ?? '').trim();
      }
      p.date_of_birth = source.date_of_birth || null;
    } else if (key === 'employment') {
      for (const f of ['employment_type_code', 'contract_type_code', 'rotation']) p[f] = String(source[f] ?? '').trim();
      p.join_date = source.join_date || null;
      p.kuwaitization = Boolean(source.kuwaitization);
      p.position = source.position ? Number(source.position) : null;
    } else if (key === 'organization') {
      p.org_unit = source.org_unit ? Number(source.org_unit) : null;
      p.manager = source.manager ? Number(source.manager) : null;
    } else if (key === 'compensation') {
      p.basic_salary = String(source.basic_salary ?? '').trim();
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
      if (canViewCompensation) Object.assign(payload, buildPayloadFrom(editAllDraft, 'compensation'));
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
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formNameEnGiven')} name="name_en_given" value={editAllDraft.name_en_given ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formNameEnFamily')} name="name_en_family" value={editAllDraft.name_en_family ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formNameArGiven')} name="name_ar_given" value={editAllDraft.name_ar_given ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formNameArFamily')} name="name_ar_family" value={editAllDraft.name_ar_family ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" select label={t('formGender')} name="gender" value={editAllDraft.gender ?? ''} onChange={handleEditAllChange}>
                <MenuItem value="">{t('fieldOptional')}</MenuItem>
                <MenuItem value="male">{t('genderMale')}</MenuItem>
                <MenuItem value="female">{t('genderFemale')}</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formCivilId')} name="civil_id" value={editAllDraft.civil_id ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" type="date" slotProps={{ inputLabel: { shrink: true } }} label={t('formDateOfBirth')} name="date_of_birth" value={editAllDraft.date_of_birth ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formNationality')} name="nationality" value={editAllDraft.nationality ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formNationalityCode')} name="nationality_code" value={editAllDraft.nationality_code ?? ''} onChange={handleEditAllChange} />
            </Grid>
          </Grid>

          <SectionHeading icon={WorkIcon} title={t('sectionEmployment')} />
          <Grid container spacing={1.5}>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formEmploymentTypeCode')} name="employment_type_code" value={editAllDraft.employment_type_code ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formContractTypeCode')} name="contract_type_code" value={editAllDraft.contract_type_code ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" type="date" slotProps={{ inputLabel: { shrink: true } }} label={t('formJoinDate')} name="join_date" value={editAllDraft.join_date ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" label={t('formRotation')} name="rotation" value={editAllDraft.rotation ?? ''} onChange={handleEditAllChange} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" select label={t('colPosition')} name="position" value={editAllDraft.position ?? ''} onChange={handleEditAllChange}>
                <MenuItem value="">{t('managerUnassigned')}</MenuItem>
                {positions.map((p) => (
                  <MenuItem key={p.id} value={p.id}>{p.title || p.code}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" select label={t('formKuwaitization')} name="kuwaitization" value={editAllDraft.kuwaitization ? 'true' : 'false'} onChange={(e) => setEditAllDraft((prev) => ({ ...prev, kuwaitization: e.target.value === 'true' }))}>
                <MenuItem value="true">{t('yes')}</MenuItem>
                <MenuItem value="false">{t('no')}</MenuItem>
              </TextField>
            </Grid>
          </Grid>

          <SectionHeading icon={BusinessIcon} title={t('sectionOrganization')} />
          <Grid container spacing={1.5}>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" select label={t('formOrgUnit')} name="org_unit" value={editAllDraft.org_unit ?? ''} onChange={handleEditAllChange}>
                <MenuItem value="">{t('managerUnassigned')}</MenuItem>
                {(emp.allOrgUnits || []).map((u) => (
                  <MenuItem key={u.id} value={u.id}>{u.name || u.code || u.id}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField fullWidth size="small" select label={t('formManager')} name="manager" value={editAllDraft.manager ?? ''} onChange={handleEditAllChange}>
                <MenuItem value="">{t('managerUnassigned')}</MenuItem>
                {(emp.allEmployees || []).filter((e) => e.id !== emp.id).map((e) => (
                  <MenuItem key={e.id} value={e.id}>{`${e.employee_no ?? '—'} — ${e.full_name ?? ''}`}</MenuItem>
                ))}
              </TextField>
            </Grid>
          </Grid>

          {canViewCompensation && (
            <>
              <SectionHeading icon={PaidIcon} title={t('sectionCompensation')} />
              <Grid container spacing={1.5}>
                <Grid item xs={12} sm={6}>
                  <TextField fullWidth size="small" type="number" inputProps={{ step: '0.001', min: '0' }} label={t('formBasicSalary')} name="basic_salary" value={editAllDraft.basic_salary ?? ''} onChange={handleEditAllChange} />
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
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formNameEnGiven')} name="name_en_given" value={draft.name_en_given ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formNameEnFamily')} name="name_en_family" value={draft.name_en_family ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formNameArGiven')} name="name_ar_given" value={draft.name_ar_given ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formNameArFamily')} name="name_ar_family" value={draft.name_ar_family ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" select label={t('formGender')} name="gender" value={draft.gender ?? ''} onChange={handleChange}>
                  <MenuItem value="">{t('fieldOptional')}</MenuItem>
                  <MenuItem value="male">{t('genderMale')}</MenuItem>
                  <MenuItem value="female">{t('genderFemale')}</MenuItem>
                </TextField>
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formCivilId')} name="civil_id" value={draft.civil_id ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" type="date" slotProps={{ inputLabel: { shrink: true } }} label={t('formDateOfBirth')} name="date_of_birth" value={draft.date_of_birth ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formNationality')} name="nationality" value={draft.nationality ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formNationalityCode')} name="nationality_code" value={draft.nationality_code ?? ''} onChange={handleChange} />
              </Grid>
            </Grid>
            <SectionActions editing onSave={() => save('identity')} onCancel={cancelEdit} saving={saving} />
          </Stack>
        ) : (
          <Box>
            <Grid container spacing={1.5}>
              <Grid item xs={6} sm={4}><ReadField label={t('formNameEnGiven')} value={emp.name_en_given} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formNameEnFamily')} value={emp.name_en_family} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formNameArGiven')} value={emp.name_ar_given} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formNameArFamily')} value={emp.name_ar_family} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formGender')} value={emp.gender} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formCivilId')} value={emp.civil_id} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formDateOfBirth')} value={formatDate(emp.date_of_birth)} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formNationality')} value={emp.nationality} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formNationalityCode')} value={emp.nationality_code} /></Grid>
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
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formEmploymentTypeCode')} name="employment_type_code" value={draft.employment_type_code ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formContractTypeCode')} name="contract_type_code" value={draft.contract_type_code ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" type="date" slotProps={{ inputLabel: { shrink: true } }} label={t('formJoinDate')} name="join_date" value={draft.join_date ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('formRotation')} name="rotation" value={draft.rotation ?? ''} onChange={handleChange} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" select label={t('colPosition')} name="position" value={draft.position ?? ''} onChange={handleChange}>
                  <MenuItem value="">{t('managerUnassigned')}</MenuItem>
                  {positions.map((p) => (
                    <MenuItem key={p.id} value={p.id}>{p.title || p.code}</MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid item xs={12} sm={6}>
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
              <Grid item xs={6} sm={4}><ReadField label={t('colEmployeeNo')} value={emp.employee_no} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formEmploymentTypeCode')} value={emp.employment_type_code} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formContractTypeCode')} value={emp.contract_type_code} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formJoinDate')} value={formatDate(emp.join_date)} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formRotation')} value={emp.rotation} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('colPosition')} value={positionTitle} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formKuwaitization')} value={emp.kuwaitization ? t('yes') : t('no')} /></Grid>
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
              {(emp.allOrgUnits || []).map((u) => (
                <MenuItem key={u.id} value={u.id}>{u.name || u.code || u.id}</MenuItem>
              ))}
            </TextField>
            <TextField fullWidth size="small" select label={t('formManager')} name="manager" value={draft.manager ?? ''} onChange={handleChange}>
              <MenuItem value="">{t('managerUnassigned')}</MenuItem>
              {(emp.allEmployees || []).filter((e) => e.id !== emp.id).map((e) => (
                <MenuItem key={e.id} value={e.id}>{`${e.employee_no ?? '—'} — ${e.full_name ?? ''}`}</MenuItem>
              ))}
            </TextField>
            <SectionActions editing onSave={() => save('organization')} onCancel={cancelEdit} saving={saving} />
          </Stack>
        ) : (
          <Box>
            <Grid container spacing={1.5}>
              <Grid item xs={6} sm={4}><ReadField label={t('formOrgUnit')} value={emp.orgUnitName} /></Grid>
              <Grid item xs={6} sm={4}><ReadField label={t('formManager')} value={managerLabel} /></Grid>
            </Grid>
            <SectionActions onEdit={() => startEdit('organization')} />
          </Box>
        )}
      </Section>

      {/* ── Compensation (Tier-2) ── */}
      <Section
        title={t('sectionCompensation')}
        icon={PaidIcon}
        summary={compSummary}
        expanded={Boolean(expanded.compensation)}
        onToggle={() => toggle('compensation')}
      >
        {editing === 'compensation' ? (
          <Stack spacing={1.5}>
            <TextField
              fullWidth
              size="small"
              type="number"
              inputProps={{ step: '0.001', min: '0' }}
              label={t('formBasicSalary')}
              name="basic_salary"
              value={draft.basic_salary ?? ''}
              onChange={handleChange}
            />
            <SectionActions editing onSave={() => save('compensation')} onCancel={cancelEdit} saving={saving} />
          </Stack>
        ) : canViewCompensation ? (
          <Box>
            <ReadField label={t('formBasicSalary')} value={emp.basic_salary != null ? formatAmount(emp.basic_salary) : '—'} />
            <SectionActions onEdit={() => startEdit('compensation')} />
          </Box>
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
