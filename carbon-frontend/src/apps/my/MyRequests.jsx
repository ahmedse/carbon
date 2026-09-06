// src/apps/my/MyRequests.jsx
// My (employee self-service) — My Requests page (route /my/requests).
// Lists the current user's own correspondence (thin slice: leave requests)
// with client-side Status/Type filter chips. Selecting a chip refetches
// GET correspondence/ with the matching query params. Rows navigate to
// /my/requests/:id.

import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, CircularProgress, Stack, Typography } from '@mui/material';
import ArticleIcon from '@mui/icons-material/Article';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchMyCorrespondence } from '../../api/my';
import { FONT } from '../../theme/themeTokens';
import RequestTable from './components/RequestTable';
import { STATUS_CODES, STATUS_SUFFIX, codeLabel } from './components/myRequestsLabels';

const LEAVE_REQUEST_TYPE = 'leave_request';

function FilterChips({ label, options, value, onChange }) {
  return (
    <Stack direction="row" alignItems="center" spacing={0.5} useFlexGap flexWrap="wrap">
      <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>{label}</Typography>
      {options.map((option) => {
        const selected = value === option.value;
        return (
          <Chip
            key={option.value}
            size="small"
            variant={selected ? 'filled' : 'outlined'}
            color={selected ? 'primary' : 'default'}
            label={option.label}
            onClick={() => onChange(option.value)}
          />
        );
      })}
    </Stack>
  );
}

FilterChips.propTypes = {
  label: PropTypes.string.isRequired,
  options: PropTypes.arrayOf(
    PropTypes.shape({ value: PropTypes.string.isRequired, label: PropTypes.string.isRequired })
  ).isRequired,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
};

export default function MyRequests() {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const navigate = useNavigate();
  useDocumentTitle(t('requestsTitle'));

  const [status, setStatus] = useState('');
  const [corrType, setCorrType] = useState('');

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchMyCorrespondence(token, {
        status: status || undefined,
        corrType: corrType || undefined,
      });
      setItems(Array.isArray(result?.items) ? result.items : []);
    } catch (err) {
      setError(err?.message || t('error'));
    } finally {
      setLoading(false);
    }
  }, [token, status, corrType, t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleOpen = useCallback((id) => navigate(`/my/requests/${id}`), [navigate]);

  const statusOptions = [
    { value: '', label: t('filterAll') },
    ...STATUS_CODES.map((code) => ({
      value: code,
      label: codeLabel(t, 'status', STATUS_SUFFIX, code),
    })),
  ];

  const typeOptions = [
    { value: '', label: t('filterAll') },
    { value: LEAVE_REQUEST_TYPE, label: t('type.leaveRequest') },
  ];

  return (
    <Box
      component="main"
      sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      <PageContainer>
        <PageHeader icon={ArticleIcon} title={t('requestsTitle')} subtitle={t('requestsSubtitle')} />
        <Stack spacing={1}>
          <Stack direction="row" alignItems="center" spacing={1.5} useFlexGap flexWrap="wrap">
            <FilterChips
              label={t('filterStatus')}
              options={statusOptions}
              value={status}
              onChange={setStatus}
            />
            <FilterChips
              label={t('filterType')}
              options={typeOptions}
              value={corrType}
              onChange={setCorrType}
            />
            {loading && <CircularProgress size={12} aria-label={t('loading')} />}
          </Stack>
          <RequestTable
            records={items}
            loading={loading}
            error={error}
            onRetry={load}
            onRowClick={handleOpen}
            hasActiveFilters={Boolean(status || corrType)}
          />
        </Stack>
      </PageContainer>
    </Box>
  );
}
