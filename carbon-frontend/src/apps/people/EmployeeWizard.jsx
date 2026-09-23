// src/apps/people/EmployeeWizard.jsx
// Employee create form — 4-step wizard (Identity → Employment → Compensation →
// Review) replacing the flat SystemDialog form. Governed enums render as
// searchable Autocomplete dropdowns over mdm.ReferenceSet (no free-text
// nationality/gender/employment/contract/rotation). Field-level help via
// MicroHelp tooltips + format hints. Per-step validation gates Next.
//
// Reuses the standard Wizard primitive (src/components/Wizard).
// NSR-7C: form stores codes under FK names; payload never emits `*_code`.

import React, { useMemo, useState } from 'react';
import EmployeePicker from './EmployeePicker';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Autocomplete,
  Box,
  FormControlLabel,
  Grid,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import Wizard from '../../components/Wizard';
import MicroHelp from '../../components/MicroHelp';
import { useReferenceOptions } from '../../hooks/useReferenceOptions';
import { orgUnitSelectOptions } from '../../api/orgUnits';
import { buildEmployeeWizardPayload } from './employeeWizardPayload';
import { refCode } from './utils';

const EMPTY_FORM = {
  org_unit: '',
  employee_no: '',
  full_name: '',
  name_en_given: '',
  name_en_family: '',
  name_ar_given: '',
  name_ar_family: '',
  nationality: '',
  gender: '',
  civil_id: '',
  date_of_birth: '',
  employment_type: '',
  contract_type: '',
  kuwaitization: false,
  basic_salary: '',
  opening_basic: '',
  join_date: '',
  rotation: '',
  position: '',
  manager: '',
  is_active: true,
};

function formFromEmployee(emp) {
  if (!emp) return { ...EMPTY_FORM };
  return {
    ...EMPTY_FORM,
    org_unit: emp.org_unit != null ? String(emp.org_unit) : '',
    employee_no: emp.employee_no || '',
    full_name: emp.full_name || '',
    name_en_given: emp.name_en_given || '',
    name_en_family: emp.name_en_family || '',
    name_ar_given: emp.name_ar_given || '',
    name_ar_family: emp.name_ar_family || '',
    nationality: refCode(emp.nationality),
    gender: refCode(emp.gender),
    civil_id: emp.civil_id || '',
    date_of_birth: emp.date_of_birth || '',
    employment_type: refCode(emp.employment_type),
    contract_type: refCode(emp.contract_type),
    kuwaitization: Boolean(emp.kuwaitization),
    basic_salary: emp.basic_salary != null ? String(emp.basic_salary) : '',
    opening_basic: '',
    join_date: emp.join_date || '',
    rotation: refCode(emp.rotation),
    position: emp.position != null ? String(emp.position) : '',
    manager: emp.manager != null ? String(emp.manager) : '',
    is_active: emp.is_active !== false,
  };
}

function formatCivilId(value) {
  const d = (value || '').replace(/\D/g, '').slice(0, 12);
  return d.replace(/(\d{4})(?=\d)/g, '$1 ').trim();
}

function OptionAutocomplete({
  value, onChange, options, label, helpKey, lang, required, placeholder,
}) {
  const selected = options.find((o) => o.value === value) || null;
  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
      <Autocomplete
        size="small"
        fullWidth
        options={options}
        value={selected}
        onChange={(e, v) => onChange(v ? v.value : '')}
        getOptionLabel={(o) => o.label}
        isOptionEqualToValue={(a, b) => a.value === b.value}
        renderInput={(params) => (
          <TextField
            {...params}
            label={label}
            required={required}
            placeholder={placeholder}
          />
        )}
      />
      {helpKey && <MicroHelp helpKey={helpKey} lang={lang} />}
    </Box>
  );
}

export default function EmployeeWizard({
  orgUnits,
  positions,
  token,
  canViewCompensation,
  saving,
  onSave,
  onCancel,
  employee,
}) {
  const { t, i18n } = useTranslation('people');
  const lang = i18n.language && i18n.language.startsWith('ar') ? 'ar' : 'en';

  const [form, setForm] = useState(() => formFromEmployee(employee));
  const [managerLabel, setManagerLabel] = useState(employee?.manager_label || '');

  const nationality = useReferenceOptions('nationality');
  const employmentType = useReferenceOptions('employment_type');
  const contractType = useReferenceOptions('contract_type');
  const gender = useReferenceOptions('gender');
  const rotation = useReferenceOptions('rotation_pattern');

  const setField = (name, value) => setForm((prev) => ({ ...prev, [name]: value }));

  const orgUnitOptions = useMemo(
    () => orgUnitSelectOptions(orgUnits),
    [orgUnits],
  );
  const positionOptions = useMemo(
    () => positions.map((p) => ({ value: String(p.id), label: p.title || p.code || String(p.id) })),
    [positions],
  );

  const civilIdDisplay = formatCivilId(form.civil_id);

  const handleCivilId = (e) => {
    setField('civil_id', (e.target.value || '').replace(/\D/g, '').slice(0, 12));
  };

  const handleKuwaitization = (e) => {
    const checked = e.target.checked;
    setForm((prev) => ({
      ...prev,
      kuwaitization: checked,
      // Helpful default: Kuwaitization implies Kuwaiti nationality unless set.
      ...(checked && !prev.nationality ? { nationality: 'KWT' } : {}),
    }));
  };

  const isCreate = !employee;
  const labelOf = (opts, val) =>
    opts.find((o) => o.value === String(val) || o.value === val)?.label || val || '—';

  const buildPayload = () => buildEmployeeWizardPayload(form, { includeOpeningBasic: isCreate });

  const civilIdValid = !form.civil_id || /^\d{12}$/.test(form.civil_id);
  const dobBeforeJoin = !(form.date_of_birth && form.join_date)
    || form.date_of_birth < form.join_date;
  const openingBasicRaw = String(form.opening_basic ?? '').trim();
  const openingBasicValid = !openingBasicRaw
    || (!Number.isNaN(Number(openingBasicRaw)) && Number(openingBasicRaw) >= 0);

  const steps = [
    {
      key: 'identity',
      label: t('sectionIdentity'),
      validate: () => {
        const errors = [];
        if (!form.full_name.trim()) errors.push(t('errFullNameRequired'));
        if (!civilIdValid) errors.push(t('errCivilIdFormat'));
        if (!dobBeforeJoin) errors.push(t('errDobBeforeJoin'));
        return { valid: errors.length === 0, errors };
      },
      content: () => (
        <Stack spacing={2}>
          <TextField
            size="small"
            label={t('colFullName')}
            value={form.full_name}
            onChange={(e) => setField('full_name', e.target.value)}
            required
            fullWidth
          />
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField size="small" label={t('formNameEnGiven')} value={form.name_en_given} onChange={(e) => setField('name_en_given', e.target.value)} fullWidth />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField size="small" label={t('formNameEnFamily')} value={form.name_en_family} onChange={(e) => setField('name_en_family', e.target.value)} fullWidth />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField size="small" label={t('formNameArGiven')} value={form.name_ar_given} onChange={(e) => setField('name_ar_given', e.target.value)} fullWidth dir="rtl" />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField size="small" label={t('formNameArFamily')} value={form.name_ar_family} onChange={(e) => setField('name_ar_family', e.target.value)} fullWidth dir="rtl" />
            </Grid>
          </Grid>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
            <TextField
              size="small"
              label={t('formCivilId')}
              value={civilIdDisplay}
              onChange={handleCivilId}
              placeholder="289 1213 0045 6"
              helperText={t('formCivilIdHint')}
              error={!civilIdValid}
              fullWidth
            />
            <MicroHelp helpKey="employee.civilId" lang={lang} />
          </Box>
          <TextField
            size="small"
            label={t('formDateOfBirth')}
            type="date"
            value={form.date_of_birth}
            onChange={(e) => setField('date_of_birth', e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
          />
          <OptionAutocomplete
            value={form.gender}
            onChange={(v) => setField('gender', v)}
            options={gender.options}
            label={t('formGender')}
            helpKey="employee.gender"
            lang={lang}
          />
          <OptionAutocomplete
            value={form.nationality}
            onChange={(v) => setField('nationality', v)}
            options={nationality.options}
            label={t('formNationality')}
            helpKey="employee.nationality"
            lang={lang}
          />
          <FormControlLabel
            control={<Switch checked={form.kuwaitization} onChange={handleKuwaitization} color="primary" />}
            label={t('formKuwaitization')}
          />
          {form.kuwaitization && form.nationality && form.nationality !== 'KWT' && (
            <Typography variant="caption" color="warning.main">
              {t('kuwaitizationHint')}
            </Typography>
          )}
        </Stack>
      ),
    },
    {
      key: 'employment',
      label: t('sectionEmployment'),
      validate: () => {
        const errors = [];
        if (!form.employee_no.trim()) errors.push(t('errEmployeeNoRequired'));
        if (!form.org_unit) errors.push(t('errOrgUnitRequired'));
        if (!form.join_date) errors.push(t('errJoinDateRequired'));
        if (!form.manager) errors.push(t('errManagerRequired'));
        return { valid: errors.length === 0, errors };
      },
      content: () => (
        <Stack spacing={2}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
            <TextField
              size="small"
              label={t('formEmployeeNo')}
              value={form.employee_no}
              onChange={(e) => setField('employee_no', e.target.value)}
              helperText={t('formEmployeeNoHint')}
              required
              fullWidth
            />
            <MicroHelp helpKey="employee.employeeNo" lang={lang} />
          </Box>
          <OptionAutocomplete
            value={form.org_unit}
            onChange={(v) => setField('org_unit', v)}
            options={orgUnitOptions}
            label={t('formOrgUnit')}
            required
          />
          <OptionAutocomplete
            value={form.position}
            onChange={(v) => setField('position', v)}
            options={positionOptions}
            label={t('colPosition')}
            placeholder={t('managerUnassigned')}
          />
          <EmployeePicker
            token={token}
            label={t('formManager')}
            value={form.manager}
            initialLabel={managerLabel}
            required
            excludeId={employee?.id}
            onChange={(id, label) => {
              setField('manager', id ? String(id) : '');
              setManagerLabel(label || '');
            }}
          />
          <OptionAutocomplete
            value={form.employment_type}
            onChange={(v) => setField('employment_type', v)}
            options={employmentType.options}
            label={t('formEmploymentType')}
            helpKey="employee.employmentType"
            lang={lang}
          />
          <OptionAutocomplete
            value={form.contract_type}
            onChange={(v) => setField('contract_type', v)}
            options={contractType.options}
            label={t('formContractType')}
            helpKey="employee.contractType"
            lang={lang}
          />
          <TextField
            size="small"
            label={t('formJoinDate')}
            type="date"
            value={form.join_date}
            onChange={(e) => setField('join_date', e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            required
            fullWidth
          />
          <OptionAutocomplete
            value={form.rotation}
            onChange={(v) => setField('rotation', v)}
            options={rotation.options}
            label={t('formRotation')}
            helpKey="employee.rotation"
            lang={lang}
          />
          <FormControlLabel
            control={<Switch checked={form.is_active} onChange={(e) => setField('is_active', e.target.checked)} color="primary" />}
            label={t('formIsActive')}
          />
        </Stack>
      ),
    },
    {
      key: 'compensation',
      label: t('sectionCompensation'),
      validate: () => {
        const errors = [];
        if (!openingBasicValid) errors.push(t('errOpeningBasicInvalid'));
        return { valid: errors.length === 0, errors };
      },
      content: () => (
        <Stack spacing={2}>
          <Alert severity="info" role="status">
            {isCreate ? t('wizardOpeningBasicIntro') : t('wizardCompViaPayTab')}
          </Alert>
          {canViewCompensation && isCreate && (
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
              <TextField
                size="small"
                label={t('formOpeningBasic')}
                type="number"
                value={form.opening_basic}
                onChange={(e) => setField('opening_basic', e.target.value)}
                helperText={t('formOpeningBasicHint')}
                error={!openingBasicValid}
                fullWidth
                slotProps={{ htmlInput: { min: 0, step: '0.001', 'data-testid': 'wizard-opening-basic' } }}
              />
              <MicroHelp helpKey="employee.basicSalary" lang={lang} />
            </Box>
          )}
          {canViewCompensation && !isCreate && (
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
              <TextField
                size="small"
                label={t('formBasicSalaryReadonly')}
                value={form.basic_salary ? form.basic_salary : '—'}
                helperText={t('wizardCompReadOnlyHint')}
                fullWidth
                disabled
                slotProps={{ htmlInput: { 'aria-readonly': true, readOnly: true } }}
                data-testid="wizard-basic-salary-readonly"
              />
              <MicroHelp helpKey="employee.basicSalary" lang={lang} />
            </Box>
          )}
        </Stack>
      ),
    },
    {
      key: 'review',
      label: t('sectionReview'),
      content: () => (
        <Stack spacing={1.5}>
          <Typography variant="subtitle2" color="text.secondary">{t('reviewIntro')}</Typography>
          <ReviewRow label={t('colFullName')} value={form.full_name || '—'} />
          <ReviewRow label={t('formEmployeeNo')} value={form.employee_no || '—'} />
          <ReviewRow label={t('formNationality')} value={labelOf(nationality.options, form.nationality)} />
          <ReviewRow label={t('formGender')} value={labelOf(gender.options, form.gender)} />
          <ReviewRow label={t('formCivilId')} value={civilIdDisplay || '—'} />
          <ReviewRow label={t('formJoinDate')} value={form.join_date || '—'} />
          <ReviewRow label={t('formManager')} value={managerLabel || '—'} />
          <ReviewRow label={t('formOrgUnit')} value={labelOf(orgUnitOptions, form.org_unit)} />
          <ReviewRow label={t('colPosition')} value={labelOf(positionOptions, form.position)} />
          <ReviewRow label={t('formEmploymentType')} value={labelOf(employmentType.options, form.employment_type)} />
          <ReviewRow label={t('formContractType')} value={labelOf(contractType.options, form.contract_type)} />
          <ReviewRow label={t('formRotation')} value={labelOf(rotation.options, form.rotation)} />
          {canViewCompensation && isCreate && (
            <ReviewRow
              label={t('formOpeningBasic')}
              value={openingBasicRaw || t('openingBasicNone')}
            />
          )}
          {canViewCompensation && !isCreate && (
            <ReviewRow
              label={t('formBasicSalaryReadonly')}
              value={form.basic_salary || t('compBasicNone')}
            />
          )}
          <Typography variant="caption" color="text.secondary">
            {isCreate ? t('wizardOnboardReadyHint') : t('wizardCompViaPayTab')}
          </Typography>
          <ReviewRow label={t('formKuwaitization')} value={form.kuwaitization ? t('yes') : t('no')} />
          <ReviewRow label={t('formIsActive')} value={form.is_active ? t('yes') : t('no')} />
        </Stack>
      ),
    },
  ];

  return (
    <Wizard
      steps={steps}
      onFinish={() => onSave(buildPayload())}
      onCancel={onCancel}
      finishLabel={t('save')}
      nextLabel={t('wizardNext')}
      backLabel={t('wizardBack')}
      cancelLabel={t('cancel')}
      submitting={saving}
    />
  );
}

function ReviewRow({ label, value }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, py: 0.5, borderBottom: 1, borderColor: 'divider' }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>{value}</Typography>
    </Box>
  );
}
