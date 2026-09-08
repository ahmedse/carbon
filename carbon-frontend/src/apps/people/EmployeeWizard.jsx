// src/apps/people/EmployeeWizard.jsx
// Employee create form — 4-step wizard (Identity → Employment → Compensation →
// Review) replacing the flat SystemDialog form. Governed enums render as
// searchable Autocomplete dropdowns over mdm.ReferenceSet (no free-text
// nationality/gender/employment/contract/rotation). Field-level help via
// MicroHelp tooltips + format hints. Per-step validation gates Next.
//
// Reuses the standard Wizard primitive (src/components/Wizard).

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
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

const EMPTY_FORM = {
  org_unit: '',
  employee_no: '',
  full_name: '',
  name_en_given: '',
  name_en_family: '',
  name_ar_given: '',
  name_ar_family: '',
  nationality: '',
  nationality_code: '',
  gender: '',
  civil_id: '',
  date_of_birth: '',
  employment_type_code: '',
  contract_type_code: '',
  kuwaitization: false,
  basic_salary: '',
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
    nationality: emp.nationality || '',
    nationality_code: emp.nationality_code || '',
    gender: emp.gender || '',
    civil_id: emp.civil_id || '',
    date_of_birth: emp.date_of_birth || '',
    employment_type_code: emp.employment_type_code || '',
    contract_type_code: emp.contract_type_code || '',
    kuwaitization: Boolean(emp.kuwaitization),
    basic_salary: emp.basic_salary != null ? String(emp.basic_salary) : '',
    join_date: emp.join_date || '',
    rotation: emp.rotation || '',
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
  employees,
  canViewCompensation,
  saving,
  onSave,
  onCancel,
  employee,
}) {
  const { t, i18n } = useTranslation('people');
  const lang = i18n.language && i18n.language.startsWith('ar') ? 'ar' : 'en';

  const [form, setForm] = useState(() => formFromEmployee(employee));

  const nationality = useReferenceOptions('nationality');
  const employmentType = useReferenceOptions('employment_type');
  const contractType = useReferenceOptions('contract_type');
  const gender = useReferenceOptions('gender');
  const rotation = useReferenceOptions('rotation_pattern');

  const setField = (name, value) => setForm((prev) => ({ ...prev, [name]: value }));

  const orgUnitOptions = useMemo(
    () => orgUnits.map((u) => ({ value: String(u.id), label: u.name || u.code || String(u.id) })),
    [orgUnits],
  );
  const positionOptions = useMemo(
    () => positions.map((p) => ({ value: String(p.id), label: p.title || p.code || String(p.id) })),
    [positions],
  );
  const managerOptions = useMemo(
    () => employees.map((e) => ({ value: String(e.id), label: `${e.employee_no} — ${e.full_name}` })),
    [employees],
  );

  const civilIdDisplay = formatCivilId(form.civil_id);

  const handleCivilId = (e) => {
    setField('civil_id', (e.target.value || '').replace(/\D/g, '').slice(0, 12));
  };

  const handleNationality = (code) => {
    const opt = nationality.options.find((o) => o.value === code);
    setForm((prev) => ({
      ...prev,
      nationality_code: code,
      nationality: opt ? opt.label : prev.nationality,
    }));
  };

  const handleKuwaitization = (e) => {
    const checked = e.target.checked;
    setForm((prev) => ({
      ...prev,
      kuwaitization: checked,
      // Helpful default: Kuwaitization implies Kuwaiti nationality unless set.
      ...(checked && !prev.nationality_code ? { nationality_code: 'KWT', nationality: 'Kuwaiti' } : {}),
    }));
  };

  const labelOf = (opts, val) =>
    opts.find((o) => o.value === String(val) || o.value === val)?.label || val || '—';

  const buildPayload = () => {
    const payload = {
      org_unit: Number(form.org_unit),
      employee_no: form.employee_no.trim(),
      full_name: form.full_name.trim(),
      join_date: form.join_date,
      is_active: Boolean(form.is_active),
      kuwaitization: Boolean(form.kuwaitization),
    };
    if (canViewCompensation) payload.basic_salary = String(form.basic_salary).trim();
    const optionalText = [
      ['nationality', form.nationality],
      ['nationality_code', form.nationality_code],
      ['gender', form.gender],
      ['civil_id', form.civil_id],
      ['date_of_birth', form.date_of_birth],
      ['employment_type_code', form.employment_type_code],
      ['contract_type_code', form.contract_type_code],
      ['rotation', form.rotation],
      ['name_en_given', form.name_en_given],
      ['name_en_family', form.name_en_family],
      ['name_ar_given', form.name_ar_given],
      ['name_ar_family', form.name_ar_family],
    ];
    for (const [key, val] of optionalText) {
      if (val && String(val).trim()) payload[key] = String(val).trim();
    }
    payload.position = form.position ? Number(form.position) : null;
    payload.manager = form.manager ? Number(form.manager) : null;
    return payload;
  };

  const civilIdValid = !form.civil_id || /^\d{12}$/.test(form.civil_id);
  const dobBeforeJoin = !(form.date_of_birth && form.join_date)
    || form.date_of_birth < form.join_date;

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
            value={form.nationality_code}
            onChange={handleNationality}
            options={nationality.options}
            label={t('formNationality')}
            helpKey="employee.nationality"
            lang={lang}
          />
          <FormControlLabel
            control={<Switch checked={form.kuwaitization} onChange={handleKuwaitization} color="primary" />}
            label={t('formKuwaitization')}
          />
          {form.kuwaitization && form.nationality_code && form.nationality_code !== 'KWT' && (
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
          <OptionAutocomplete
            value={form.manager}
            onChange={(v) => setField('manager', v)}
            options={managerOptions}
            label={t('formManager')}
            placeholder={t('managerUnassigned')}
          />
          <OptionAutocomplete
            value={form.employment_type_code}
            onChange={(v) => setField('employment_type_code', v)}
            options={employmentType.options}
            label={t('formEmploymentType')}
            helpKey="employee.employmentType"
            lang={lang}
          />
          <OptionAutocomplete
            value={form.contract_type_code}
            onChange={(v) => setField('contract_type_code', v)}
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
        if (canViewCompensation) {
          if (!String(form.basic_salary).trim()) errors.push(t('errBasicSalaryRequired'));
          else if (Number(form.basic_salary) < 0) errors.push(t('errBasicSalaryNegative'));
        }
        return { valid: errors.length === 0, errors };
      },
      content: () => (
        <Stack spacing={2}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
            <TextField
              size="small"
              label={t('formBasicSalary')}
              value={form.basic_salary}
              onChange={(e) => setField('basic_salary', e.target.value)}
              type="number"
              inputProps={{ step: '0.001', min: '0' }}
              helperText={t('formBasicSalaryHint')}
              required
              fullWidth
            />
            <MicroHelp helpKey="employee.basicSalary" lang={lang} />
          </Box>
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
          <ReviewRow label={t('formNationality')} value={labelOf(nationality.options, form.nationality_code)} />
          <ReviewRow label={t('formGender')} value={labelOf(gender.options, form.gender)} />
          <ReviewRow label={t('formCivilId')} value={civilIdDisplay || '—'} />
          <ReviewRow label={t('formJoinDate')} value={form.join_date || '—'} />
          <ReviewRow label={t('formOrgUnit')} value={labelOf(orgUnitOptions, form.org_unit)} />
          <ReviewRow label={t('colPosition')} value={labelOf(positionOptions, form.position)} />
          <ReviewRow label={t('formEmploymentType')} value={labelOf(employmentType.options, form.employment_type_code)} />
          <ReviewRow label={t('formContractType')} value={labelOf(contractType.options, form.contract_type_code)} />
          <ReviewRow label={t('formRotation')} value={labelOf(rotation.options, form.rotation)} />
          {canViewCompensation && <ReviewRow label={t('formBasicSalary')} value={form.basic_salary || '—'} />}
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
