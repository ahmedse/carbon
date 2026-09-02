// src/apps/people/PeopleConfigPage.jsx
// People & Payroll — app configuration (read-only): identity, roles & compliance rules.

import React, { useEffect, useState } from 'react';
import {
  Box,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import peopleManifest from './manifest';
import { fetchComplianceRules } from '../../api/people';
import { formatDate } from './utils';

// App identity fields shown in the two-column key/value layout.
const IDENTITY_FIELDS = [
  { key: 'id', labelKey: 'colId' },
  { key: 'name', labelKey: 'colName' },
  { key: 'version', labelKey: 'colVersion' },
  { key: 'description', labelKey: 'colDescription' },
  { key: 'routePrefix', labelKey: 'colRoutePrefix' },
  { key: 'apiPrefix', labelKey: 'colApiPrefix' },
];

export default function PeopleConfigPage() {
  const { t } = useTranslation('people');
  useDocumentTitle(t('configTitle'));
  const { token } = useAuth();
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchComplianceRules(token)
      .then((data) => setRules(Array.isArray(data?.results) ? data.results : []))
      .catch((err) => setError(err?.message || t('configLoadError')))
      .finally(() => setLoading(false));
  }, [token, t]);

  return (
    <PageContainer>
      <PageHeader icon={SettingsIcon} title={t('configTitle')} subtitle={t('configSubtitle')} />

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

        {/* Compliance Rules */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, mb: 1 }}>{t('configComplianceRules')}</Typography>
          {loading ? (
            <LoadingSkeleton variant="table" />
          ) : error ? (
            <ErrorAlert message={error} onRetry={() => window.location.reload()} />
          ) : rules.length === 0 ? (
            <EmptyState icon={<SettingsIcon />} title={t('configEmpty')} description={t('configEmptyDesc')} />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colRuleId')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colVersion')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colName')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colJurisdiction')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colCategory')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colEffectiveDate')}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('colAuthoritative')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rules.map((rule) => (
                    <TableRow key={rule.id} hover>
                      <TableCell>{rule.rule_id ?? '—'}</TableCell>
                      <TableCell>{rule.version ?? '—'}</TableCell>
                      <TableCell>{rule.name ?? '—'}</TableCell>
                      <TableCell>{rule.jurisdiction ?? '—'}</TableCell>
                      <TableCell>{rule.category ?? '—'}</TableCell>
                      <TableCell>{formatDate(rule.effective_date)}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={rule.is_authoritative ? 'success' : 'default'}
                          label={rule.is_authoritative ? t('yes') : t('no')}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      </Stack>
    </PageContainer>
  );
}
