// src/apps/people/PeopleConfigPage.jsx
// People & Payroll — App Config hub. Tabs: Overview (identity + roles),
// Reference Data, Compliance Rules (CRUD), Compensation (components + plans).

import React, { useState } from 'react';
import {
  Box,
  Chip,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import peopleManifest from './manifest';
import ReferenceDataManager from './ReferenceDataManager';
import ComplianceRulesPanel from './ComplianceRulesPanel';
import CompensationConfigPanel from './CompensationConfigPanel';

// App identity fields shown in the two-column key/value layout.
const IDENTITY_FIELDS = [
  { key: 'id', labelKey: 'colId' },
  { key: 'name', labelKey: 'colName' },
  { key: 'version', labelKey: 'colVersion' },
  { key: 'description', labelKey: 'colDescription' },
  { key: 'routePrefix', labelKey: 'colRoutePrefix' },
  { key: 'apiPrefix', labelKey: 'colApiPrefix' },
];

const TAB_STORAGE_KEY = 'carbon-people-config-tab';
const TAB_KEYS = ['Overview', 'Reference', 'Compliance', 'Compensation'];

export default function PeopleConfigPage() {
  const { t } = useTranslation('people');
  useDocumentTitle(t('configTitle'));
  const [tabIndex, setTabIndex] = useState(() => {
    const saved = parseInt(localStorage.getItem(TAB_STORAGE_KEY) ?? '0', 10);
    return Number.isFinite(saved) && saved < TAB_KEYS.length ? saved : 0;
  });
  const handleTabChange = (_, v) => { setTabIndex(v); localStorage.setItem(TAB_STORAGE_KEY, String(v)); };

  const overviewTab = (
    <Stack spacing={2}>
      {/* App Identity */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>{t('configAppIdentity')}</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
          {IDENTITY_FIELDS.map((field) => (
            <Box key={field.key}>
              <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary', textTransform: 'uppercase' }}>
                {t(field.labelKey)}
              </Typography>
              <Typography sx={{ fontSize: '0.875rem' }}>{peopleManifest[field.key] ?? '—'}</Typography>
            </Box>
          ))}
        </Box>
      </Paper>

      {/* Roles */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>{t('configRoles')}</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colRoleKey')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colRoleLabel')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colRoleScoped')}</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colDescription')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(peopleManifest.roles || []).map((role) => (
                <TableRow key={role.key} hover>
                  <TableCell>{role.key ?? '—'}</TableCell>
                  <TableCell>{role.label ?? '—'}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      variant="outlined"
                      color={role.scoped ? 'info' : 'default'}
                      label={role.scoped ? t('yes') : t('no')}
                    />
                  </TableCell>
                  <TableCell>{role.description ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Stack>
  );

  return (
    <PageContainer>
      <PageHeader icon={SettingsIcon} title={t('configTitle')} subtitle={t('configSubtitle')} />

      <Tabs value={tabIndex} onChange={handleTabChange} sx={{ mb: 1.5, borderBottom: 1, borderColor: 'divider' }}>
        {TAB_KEYS.map((k) => (
          <Tab
            key={k}
            label={t(`configTab${k}`)}
            sx={{ minHeight: 36, fontSize: '0.8125rem', textTransform: 'none', py: 0.75 }}
          />
        ))}
      </Tabs>

      {tabIndex === 0 && overviewTab}
      {tabIndex === 1 && <ReferenceDataManager />}
      {tabIndex === 2 && <ComplianceRulesPanel />}
      {tabIndex === 3 && <CompensationConfigPanel />}
    </PageContainer>
  );
}
