// src/apps/people/tabs/EmployeeOverviewTab.jsx
// Employee profile — read-only overview with Identity + Employment sections.
// Receives the loaded employee plus resolved labels via `entityData`.

import React from 'react';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { formatAmount, formatDate } from '../utils';

function DetailRow({ label, value }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, py: 0.25 }}>
      <Typography sx={{ fontSize: '0.8125rem', color: 'text.secondary', fontWeight: 600, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: '0.8125rem', textAlign: 'right', overflowWrap: 'anywhere' }}>
        {value}
      </Typography>
    </Box>
  );
}

export default function EmployeeOverviewTab({ entityData }) {
  const { t } = useTranslation('people');
  const employee = entityData || {};

  const identityRows = [
    { label: t('formNameEnGiven'), value: employee.name_en_given || '—' },
    { label: t('formNameEnFamily'), value: employee.name_en_family || '—' },
    { label: t('formNameArGiven'), value: employee.name_ar_given || '—' },
    { label: t('formNameArFamily'), value: employee.name_ar_family || '—' },
    { label: t('formCivilId'), value: employee.civil_id || '—' },
    { label: t('formDateOfBirth'), value: formatDate(employee.date_of_birth) },
    { label: t('formGender'), value: employee.gender || '—' },
    { label: t('formNationalityCode'), value: employee.nationality_code || '—' },
  ];

  const employmentRows = [
    { label: t('colEmployeeNo'), value: employee.employee_no || '—' },
    { label: t('colFullName'), value: employee.full_name || '—' },
    { label: t('formOrgUnit'), value: employee.orgUnitName || '—' },
    { label: t('formManager'), value: employee.managerLabel || '—' },
    { label: t('formBasicSalary'), value: formatAmount(employee.basic_salary) },
    { label: t('formJoinDate'), value: formatDate(employee.join_date) },
    { label: t('formEmploymentTypeCode'), value: employee.employment_type_code || '—' },
    { label: t('formContractTypeCode'), value: employee.contract_type_code || '—' },
    { label: t('formRotation'), value: employee.rotation || '—' },
    { label: t('colNationality'), value: employee.nationality || '—' },
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.secondary', mb: 1 }}>
        {t('sectionIdentity')}
      </Typography>
      <Stack spacing={0.5} sx={{ mb: 3 }}>
        {identityRows.map((row) => (
          <DetailRow key={row.label} label={row.label} value={row.value} />
        ))}
      </Stack>

      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.secondary', mb: 1 }}>
        {t('sectionEmployment')}
      </Typography>
      <Stack spacing={0.5}>
        {employmentRows.map((row) => (
          <DetailRow key={row.label} label={row.label} value={row.value} />
        ))}
        <DetailRow
          label={t('formKuwaitization')}
          value={
            <Chip
              size="small"
              variant="outlined"
              color={employee.kuwaitization ? 'success' : 'default'}
              label={employee.kuwaitization ? t('statusActive') : t('statusInactive')}
            />
          }
        />
      </Stack>
    </Box>
  );
}
