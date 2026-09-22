// src/apps/people/tabs/EmployeeRequestsTab.jsx
// HR 360 "Requests" tab — the employee's full correspondence (leave, loans,
// memos, …). Fetches the OF-16 employee correspondence list, renders a compact
// paginated table with status/type filters, and a detail dialog that reuses the
// shared my-app components (SummaryCard + ApproverChainStepper/WorkflowGraph +
// RequestTimeline). Gated by people:view (PeopleAccess mirror).

import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  MenuItem,
  Paper,
  Select,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import AssignmentIcon from '@mui/icons-material/Assignment';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../../auth/AuthContext';
import {
  fetchEmployeeCorrespondence,
  fetchEmployeeCorrespondenceDetail,
} from '../../../api/people';
import { PEOPLE_VIEW, hasCap, expandCapabilities } from '../../../capabilities';
import EmptyState from '../../../components/Page/EmptyState';
import LoadingSkeleton from '../../../components/Page/LoadingSkeleton';
import SystemDialog from '../../../components/SystemDialog';
import SummaryCard from '../../my/components/SummaryCard';
import ApproverChainStepper from '../../my/components/ApproverChainStepper';
import WorkflowGraph from '../../my/components/WorkflowGraph';
import RequestTimeline from '../../my/components/RequestTimeline';
import {
  STATUS_COLOR,
  STATUS_SUFFIX,
  CORR_TYPES,
  STATUS_CODES,
  codeLabel,
  corrTypeLabel,
  requestTypeLabel,
  formatDate,
} from '../../my/components/myRequestsLabels';

export default function EmployeeRequestsTab({ entityData }) {
  const { t, i18n } = useTranslation('people');
  const { t: tMy } = useTranslation('my');
  const { token, isGlobalAdminFlag, userCapabilities } = useAuth();

  const emp = entityData || {};
  const empId = emp.empId ?? emp.id;

  // people:view gate — mirrors PeopleAccess on the backend. Global admins bypass.
  // me_context returns capability objects ({key, …}), so extract keys first.
  const capKeys = useMemo(
    () => (Array.isArray(userCapabilities) ? userCapabilities : []).map(
      (c) => (typeof c === 'string' ? c : (c?.key || c?.capability)),
    ),
    [userCapabilities],
  );
  const canView =
    isGlobalAdminFlag === true || hasCap(expandCapabilities(capKeys), PEOPLE_VIEW);

  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const [selected, setSelected] = useState(null);
  const [view, setView] = useState('graph');
  const [events, setEvents] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!empId || !token || !canView) {
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    setError(null);
    setForbidden(false);
    fetchEmployeeCorrespondence(empId, token)
      .then((data) => {
        if (cancelled) return;
        setRecords(Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []));
      })
      .catch((err) => {
        if (cancelled) return;
        if (err?.status === 403) setForbidden(true);
        else setError(err?.message || t('requestsLoadError'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [empId, token, canView, reloadToken, t]);

  const statusOptions = useMemo(
    () => STATUS_CODES.map((code) => ({ code, label: codeLabel(tMy, 'status', STATUS_SUFFIX, code) })),
    [tMy],
  );

  const typeOptions = useMemo(
    () => CORR_TYPES.map((code) => ({ code, label: corrTypeLabel(tMy, code) })),
    [tMy],
  );

  const filtered = useMemo(() => {
    const list = Array.isArray(records) ? records : [];
    return list.filter((row) => {
      if (statusFilter !== 'all' && row.status !== statusFilter) return false;
      if (typeFilter !== 'all' && row.corr_type_code !== typeFilter) return false;
      return true;
    });
  }, [records, statusFilter, typeFilter]);

  const paginated = useMemo(() => {
    const start = page * rowsPerPage;
    return filtered.slice(start, start + rowsPerPage);
  }, [filtered, page, rowsPerPage]);

  const handleStatusFilter = (event) => {
    setStatusFilter(event.target.value);
    setPage(0);
  };
  const handleTypeFilter = (event) => {
    setTypeFilter(event.target.value);
    setPage(0);
  };
  const handleChangePage = (event, newPage) => setPage(newPage);
  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const openDetail = (row) => {
    setSelected(row);
    setView('stepper');
    setEvents([]);
    setDetailLoading(true);
    if (!row?.id || !token) {
      setDetailLoading(false);
      return;
    }
    fetchEmployeeCorrespondenceDetail(empId, row.id, token)
      .then((data) => setEvents(Array.isArray(data?.events) ? data.events : []))
      .catch(() => setEvents([]))
      .finally(() => setDetailLoading(false));
  };

  const closeDetail = () => {
    setSelected(null);
    setEvents([]);
    setView('graph');
    setDetailLoading(false);
  };

  const handleViewChange = (event, next) => {
    if (next !== null) setView(next);
  };

  const handleRowKeyDown = (event, row) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openDetail(row);
    }
  };

  if (!canView || forbidden) return null;

  return (
    <Box sx={{ p: 2 }}>
      {loading ? (
        <LoadingSkeleton variant="table" />
      ) : error ? (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => setReloadToken((n) => n + 1)}>
              {t('requestsRetry')}
            </Button>
          }
        >
          {error}
        </Alert>
      ) : records.length === 0 ? (
        <EmptyState
          icon={<AssignmentIcon />}
          title={t('requestsEmpty')}
          description={t('requestsEmptyDesc')}
        />
      ) : (
        <>
          {/* Filters */}
          <Stack
            direction="row"
            spacing={1.5}
            useFlexGap
            flexWrap="wrap"
            alignItems="center"
            sx={{ mb: 1.5 }}
          >
            <Box>
              <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary', mb: 0.25 }}>
                {t('requestsFilterStatus')}
              </Typography>
              <Select
                size="small"
                value={statusFilter}
                onChange={handleStatusFilter}
                sx={{ minWidth: 150, fontSize: '0.75rem' }}
              >
                <MenuItem value="all">{t('requestsFilterAllStatuses')}</MenuItem>
                {statusOptions.map((opt) => (
                  <MenuItem key={opt.code} value={opt.code}>{opt.label}</MenuItem>
                ))}
              </Select>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary', mb: 0.25 }}>
                {t('requestsFilterType')}
              </Typography>
              <Select
                size="small"
                value={typeFilter}
                onChange={handleTypeFilter}
                sx={{ minWidth: 150, fontSize: '0.75rem' }}
              >
                <MenuItem value="all">{t('requestsFilterAllTypes')}</MenuItem>
                {typeOptions.map((opt) => (
                  <MenuItem key={opt.code} value={opt.code}>{opt.label}</MenuItem>
                ))}
              </Select>
            </Box>
          </Stack>

          {filtered.length === 0 ? (
            <EmptyState title={t('requestsEmptyFiltered')} description={t('requestsEmptyDesc')} />
          ) : (
            <Paper variant="outlined">
              <TableContainer>
                <Table size="small" aria-busy={loading}>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>{t('colRequestsReference')}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{t('colRequestsType')}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{t('colRequestsTitle')}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{t('colRequestsStatus')}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{t('colRequestsCreated')}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{t('colRequestsResolved')}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {paginated.map((row) => (
                      <TableRow
                        key={row.id}
                        hover
                        onClick={() => openDetail(row)}
                        onKeyDown={(event) => handleRowKeyDown(event, row)}
                        role="button"
                        tabIndex={0}
                        aria-label={t('requestsOpenRequest', { ref: row.reference_no || row.id })}
                        sx={{
                          cursor: 'pointer',
                          '&:focus-visible': {
                            outline: '2px solid',
                            outlineColor: 'primary.main',
                            outlineOffset: -2,
                          },
                        }}
                      >
                        <TableCell sx={{ fontSize: '0.75rem' }} dir="ltr">
                          {row.reference_no || '—'}
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.75rem' }}>{requestTypeLabel(tMy, row)}</TableCell>
                        <TableCell sx={{ fontSize: '0.75rem' }}>{row.title || '—'}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            variant="outlined"
                            color={STATUS_COLOR[row.status] || 'default'}
                            label={codeLabel(tMy, 'status', STATUS_SUFFIX, row.status)}
                          />
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.75rem' }}>
                          {formatDate(row.created_at, i18n.language)}
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.75rem' }}>
                          {formatDate(row.resolved_at, i18n.language)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <TablePagination
                component="div"
                count={filtered.length}
                page={page}
                onPageChange={handleChangePage}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={handleChangeRowsPerPage}
                rowsPerPageOptions={[10, 25, 50]}
                labelRowsPerPage={t('requestsRowsPerPage')}
                labelDisplayedRows={({ from, to, count }) => t('requestsRowsShown', { from, to, count })}
                sx={{ fontSize: '0.75rem' }}
              />
            </Paper>
          )}
        </>
      )}

      {/* Detail dialog (conditionally rendered content = lazy-loaded) */}
      <SystemDialog
        open={Boolean(selected)}
        title={t('requestsDetailTitle')}
        onClose={closeDetail}
        onCancel={closeDetail}
        cancelLabel={t('requestsClose')}
        width={780}
        height={660}
      >
        {selected ? (
          <Stack spacing={1.5}>
            <SummaryCard item={selected} />
            <Stack direction="row" justifyContent="flex-end">
              <ToggleButtonGroup
                value={view}
                exclusive
                size="small"
                onChange={handleViewChange}
                aria-label={t('requestsViewToggleLabel')}
              >
                <ToggleButton value="stepper">{t('requestsViewStepper')}</ToggleButton>
                <ToggleButton value="graph">{t('requestsViewGraph')}</ToggleButton>
              </ToggleButtonGroup>
            </Stack>
            {view === 'stepper' ? (
              <ApproverChainStepper
                chain={selected.approver_chain}
                currentStep={selected.current_step}
                status={selected.status}
              />
            ) : (
              <WorkflowGraph
                chain={selected.approver_chain}
                currentStep={selected.current_step}
                status={selected.status}
              />
            )}
            {detailLoading ? (
              <Stack spacing={1}>
                <Skeleton variant="rounded" height={64} />
              </Stack>
            ) : (
              <RequestTimeline events={events} />
            )}
          </Stack>
        ) : null}
      </SystemDialog>
    </Box>
  );
}
