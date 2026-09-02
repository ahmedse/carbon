// src/apps/people/tabs/EmployeeEditTab.jsx
// Employee profile — editable form. Only PATCHes profile fields (identity,
// codes, manager, kuwaitization). employee_no / full_name / org_unit stay
// managed by the list page's create/edit dialog and are shown read-only here.

import React, { useState } from 'react';
import { Box, Button, FormControlLabel, MenuItem, Stack, Switch, TextField } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { updateEmployee } from '../../../api/people';

export default function EmployeeEditTab({ entityData, additionalProps }) {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { user } = useAuth();
  const { notify } = useNotification();
  const employee = entityData || {};

  const [form, setForm] = useState(() => ({
    name_en_given: employee.name_en_given ?? '',
    name_en_family: employee.name_en_family ?? '',
    name_ar_given: employee.name_ar_given ?? '',
    name_ar_family: employee.name_ar_family ?? '',
    civil_id: employee.civil_id ?? '',
    date_of_birth: employee.date_of_birth ? String(employee.date_of_birth).slice(0, 10) : '',
    gender: employee.gender ?? '',
    nationality_code: employee.nationality_code ?? '',
    employment_type_code: employee.employment_type_code ?? '',
    contract_type_code: employee.contract_type_code ?? '',
    manager: employee.manager ?? '',
    kuwaitization: Boolean(employee.kuwaitization),
    nationality: employee.nationality ?? '',
    basic_salary: employee.basic_salary != null ? String(employee.basic_salary) : '',
    join_date: employee.join_date ? String(employee.join_date).slice(0, 10) : '',
    rotation: employee.rotation ?? '',
    is_active: Boolean(employee.is_active),
  }));
  const [saving, setSaving] = useState(false);

  const handleChange = (event) => {
    const { name, value, checked, type } = event.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSave = async () => {
    if (!employee.id || !user?.token) return;

    const payload = {
      name_en_given: form.name_en_given.trim(),
      name_en_family: form.name_en_family.trim(),
      name_ar_given: form.name_ar_given.trim(),
      name_ar_family: form.name_ar_family.trim(),
      civil_id: form.civil_id.trim(),
      date_of_birth: form.date_of_birth || null,
      gender: form.gender.trim(),
      // Codes are validated server-side against mdm.ReferenceSet;
      // dropdown wiring is a later enhancement.
      nationality_code: form.nationality_code.trim(),
      employment_type_code: form.employment_type_code.trim(),
      contract_type_code: form.contract_type_code.trim(),
      manager: form.manager === '' ? null : Number(form.manager),
      kuwaitization: Boolean(form.kuwaitization),
    };

    setSaving(true);
    try {
      await updateEmployee(employee.id, payload, user.token);
      notify({ message: t('profileSaved'), type: 'success' });
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

  const managerOptions = (employee.allEmployees || []).filter((e) => e.id !== employee.id);

  return (
    <Box sx={{ p: 3, maxWidth: 480 }}>
      <Stack spacing={2}>
        <TextField label={t('colEmployeeNo')} value={employee.employee_no ?? '—'} disabled fullWidth />
        <TextField label={t('colFullName')} value={employee.full_name ?? '—'} disabled fullWidth />
        <TextField label={t('formOrgUnit')} value={employee.orgUnitName || '—'} disabled fullWidth />

        <TextField
          label={t('formNameEnGiven')}
          name="name_en_given"
          value={form.name_en_given}
          onChange={handleChange}
          fullWidth
        />
        <TextField
          label={t('formNameEnFamily')}
          name="name_en_family"
          value={form.name_en_family}
          onChange={handleChange}
          fullWidth
        />
        <TextField
          label={t('formNameArGiven')}
          name="name_ar_given"
          value={form.name_ar_given}
          onChange={handleChange}
          fullWidth
        />
        <TextField
          label={t('formNameArFamily')}
          name="name_ar_family"
          value={form.name_ar_family}
          onChange={handleChange}
          fullWidth
        />
        <TextField
          label={t('formCivilId')}
          name="civil_id"
          value={form.civil_id}
          onChange={handleChange}
          fullWidth
        />
        <TextField
          label={t('formDateOfBirth')}
          name="date_of_birth"
          value={form.date_of_birth}
          onChange={handleChange}
          type="date"
          slotProps={{ inputLabel: { shrink: true } }}
          fullWidth
        />
        <TextField
          label={t('formGender')}
          name="gender"
          value={form.gender}
          onChange={handleChange}
          fullWidth
        />
        <TextField
          label={t('formNationalityCode')}
          name="nationality_code"
          value={form.nationality_code}
          onChange={handleChange}
          fullWidth
        />
        {/* Codes are validated server-side against mdm.ReferenceSet; dropdown wiring is a later enhancement. */}
        <TextField
          label={t('formEmploymentTypeCode')}
          name="employment_type_code"
          value={form.employment_type_code}
          onChange={handleChange}
          fullWidth
        />
        <TextField
          label={t('formContractTypeCode')}
          name="contract_type_code"
          value={form.contract_type_code}
          onChange={handleChange}
          fullWidth
        />
        <TextField
          select
          label={t('formManager')}
          name="manager"
          value={form.manager ?? ''}
          onChange={handleChange}
          fullWidth
        >
          <MenuItem value="">{t('managerUnassigned')}</MenuItem>
          {managerOptions.map((e) => (
            <MenuItem key={e.id} value={e.id}>
              {`${e.employee_no ?? '—'} — ${e.full_name ?? ''}`}
            </MenuItem>
          ))}
        </TextField>
        <FormControlLabel
          control={
            <Switch
              checked={form.kuwaitization}
              onChange={handleChange}
              name="kuwaitization"
              color="primary"
            />
          }
          label={t('formKuwaitization')}
        />
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {tCommon('save')}
          </Button>
        </Box>
      </Stack>
    </Box>
  );
}
