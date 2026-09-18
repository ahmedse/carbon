// src/apps/my/components/RequestTable.jsx
// Presentational — a compact table of the current user's correspondence
// (thin slice: leave requests). Clickable rows navigate to the detail view.
// Status/type labels are derived from `status` / `subject_type` codes (never
// the integer `corr_type` PK). Color never stands alone — a text label always
// accompanies the chip.

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Card,
  CardContent,
  Chip,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import AssignmentIcon from '@mui/icons-material/Assignment';
import { useTranslation } from 'react-i18next';
import ResponsiveList from '../../../components/layout/ResponsiveList';
import { SectionTitle, InlineError } from './myRequestsCommon';
import {
  STATUS_COLOR,
  STATUS_SUFFIX,
  codeLabel,
  requestTypeLabel,
  payloadSummary,
  formatDate,
} from './myRequestsLabels';
import { FONT } from '../../../theme/themeTokens';

export default function RequestTable({
  records,
  loading,
  error,
  onRetry,
  onRowClick,
  hasActiveFilters,
}) {
  const { t, i18n } = useTranslation('my');

  const sorted = useMemo(() => {
    const list = Array.isArray(records) ? records : [];
    return [...list].sort((a, b) => {
      const aKey = String(a.created_at || a.updated_at || '');
      const bKey = String(b.created_at || b.updated_at || '');
      return bKey.localeCompare(aKey);
    });
  }, [records]);

  const handleKeyDown = (event, id) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onRowClick(id);
    }
  };

  // Skeleton only on first load (no data yet); a refetch keeps the rows
  // visible and just dims them while the filter-row spinner runs.
  const showInitialSkeleton = loading && sorted.length === 0;

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={AssignmentIcon} title={t('requestsTitle')} />
        {showInitialSkeleton ? (
          <Stack spacing={0.5} aria-label={t('loading')}>
            <Skeleton />
            <Skeleton width="70%" />
            <Skeleton width="85%" />
          </Stack>
        ) : error ? (
          <InlineError message={error} onRetry={onRetry} />
        ) : sorted.length === 0 ? (
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {hasActiveFilters ? t('requestsEmptyFiltered') : t('requestsEmpty')}
          </Typography>
        ) : (
          <ResponsiveList
            items={sorted}
            getKey={(row) => row.id}
            emptyLabel={hasActiveFilters ? t('requestsEmptyFiltered') : t('requestsEmpty')}
            renderCard={(row) => ({
              title: requestTypeLabel(t, row) || row.subject || row.title || '—',
              status: codeLabel(t, 'status', STATUS_SUFFIX, row.status),
              statusColor: STATUS_COLOR[row.status] || 'default',
              meta: formatDate(row.created_at, i18n.language),
              onClick: () => onRowClick(row.id),
            })}
            table={
              <TableContainer>
                <Table size="small" aria-busy={loading}>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableReferenceNo')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableType')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableTitle')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableSummary')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableStatus')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableCreated')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableUpdated')}
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sorted.map((row) => (
                      <TableRow
                        key={row.id}
                        hover
                        onClick={() => onRowClick(row.id)}
                        onKeyDown={(event) => handleKeyDown(event, row.id)}
                        role="button"
                        tabIndex={0}
                        aria-label={t('openRequest', { ref: row.reference_no || row.id })}
                        sx={{ cursor: 'pointer', opacity: loading ? 0.6 : 1 }}
                      >
                        <TableCell sx={{ ...FONT.body2 }}>
                          {row.reference_no || '—'}
                        </TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>
                          {requestTypeLabel(t, row)}
                        </TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>
                          {row.title || '—'}
                        </TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>
                          {payloadSummary(t, row, i18n.language) || '—'}
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            variant="outlined"
                            color={STATUS_COLOR[row.status] || 'default'}
                            label={codeLabel(t, 'status', STATUS_SUFFIX, row.status)}
                          />
                        </TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>
                          {formatDate(row.created_at, i18n.language)}
                        </TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>
                          {formatDate(row.updated_at, i18n.language)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            }
          />
        )}
      </CardContent>
    </Card>
  );
}

RequestTable.propTypes = {
  records: PropTypes.array.isRequired,
  loading: PropTypes.bool.isRequired,
  error: PropTypes.string,
  onRetry: PropTypes.func,
  onRowClick: PropTypes.func.isRequired,
  hasActiveFilters: PropTypes.bool.isRequired,
};

RequestTable.defaultProps = {
  error: null,
  onRetry: null,
};
