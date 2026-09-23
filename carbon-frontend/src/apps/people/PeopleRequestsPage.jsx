// People audit register — every employee request (leave, loan, attendance
// permission, profile change, memo). Search and filters hit the server.
// The eye opens the request page. Row click only highlights the row.
// Decision buttons live on that page, and only for the current approver.

import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Chip, IconButton, Tooltip } from '@mui/material';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { fetchEmployees, fetchRequestAudit } from '../../api/people';
import { fetchOrgUnits } from '../../api/catalog';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import {
  STATUS_CODES,
  STATUS_COLOR,
  STATUS_SUFFIX,
  ROLE_SUFFIX,
  CORR_FILTER_TYPES,
  codeLabel,
  corrTypeLabel,
  displayTitle,
  requestTypeLabel,
  formatDate,
} from '../my/components/myRequestsLabels';

const PAGE_SIZE = 25;
const SERVER_OPTIONS = (options) => options;

function employeeOption(emp) {
  if (!emp) return null;
  return {
    value: emp.id,
    label: emp.full_name || emp.employee_no || String(emp.id),
  };
}

function useEmployeeSearch(token, query, pinned) {
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await fetchEmployees(token, { q: query, page: 1, page_size: 20 });
        const rows = Array.isArray(data) ? data : data?.results || [];
        const mapped = rows.map(employeeOption).filter(Boolean);
        if (pinned && !mapped.some((opt) => opt.value === pinned.value)) {
          mapped.unshift(pinned);
        }
        if (!cancelled) setOptions(mapped);
      } catch {
        if (!cancelled) setOptions(pinned ? [pinned] : []);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [token, query, pinned]);

  return { options, loading };
}

export default function PeopleRequestsPage() {
  const { t, i18n } = useTranslation('people');
  const { t: tMy } = useTranslation('my');
  const { t: tCommon } = useTranslation('common');
  const navigate = useNavigate();
  const { token } = useAuth();

  const [rows, setRows] = useState([]);
  const [rowCount, setRowCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [highlightId, setHighlightId] = useState(null);

  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({
    corr_type: '',
    status: '',
    org_unit: '',
    employee: '',
    manager: '',
  });
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: PAGE_SIZE });

  const [orgUnits, setOrgUnits] = useState([]);
  const [employeeQuery, setEmployeeQuery] = useState('');
  const [managerQuery, setManagerQuery] = useState('');
  const [employeeChoice, setEmployeeChoice] = useState(null);
  const [managerChoice, setManagerChoice] = useState(null);

  const employeeSearch = useEmployeeSearch(token, employeeQuery, employeeChoice);
  const managerSearch = useEmployeeSearch(token, managerQuery, managerChoice);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setPaginationModel((prev) => (prev.page === 0 ? prev : { ...prev, page: 0 }));
  }, [search, filters]);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    fetchOrgUnits(token)
      .then((data) => {
        if (!cancelled) setOrgUnits(Array.isArray(data) ? data : data?.results || []);
      })
      .catch(() => {
        if (!cancelled) setOrgUnits([]);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = {
      page: paginationModel.page + 1,
      page_size: paginationModel.pageSize,
    };
    if (search) params.q = search;
    if (filters.corr_type) params.corr_type = filters.corr_type;
    if (filters.status) params.status = filters.status;
    if (filters.org_unit) params.org_unit = filters.org_unit;
    if (filters.employee) params.employee = filters.employee;
    if (filters.manager) params.manager = filters.manager;

    fetchRequestAudit(token, params)
      .then((data) => {
        if (cancelled) return;
        setRows(data.items);
        setRowCount(data.count);
      })
      .catch((err) => {
        if (cancelled) return;
        setRows([]);
        setRowCount(0);
        setError(err?.message || t('requestsAuditLoadError'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, search, filters, paginationModel, reloadToken, t]);

  const filterDefs = useMemo(() => [
    {
      key: 'corr_type',
      label: t('filterRequestType'),
      options: CORR_FILTER_TYPES.map((code) => ({
        value: code,
        label: corrTypeLabel(tMy, code),
      })),
    },
    {
      key: 'status',
      label: t('filterStatus'),
      options: STATUS_CODES.map((code) => ({
        value: code,
        label: codeLabel(tMy, 'status', STATUS_SUFFIX, code),
      })),
    },
    {
      key: 'org_unit',
      label: t('filterRequestOrgUnit'),
      options: orgUnits.map((unit) => ({ value: unit.id, label: unit.name })),
    },
    {
      key: 'employee',
      label: t('filterRequestEmployee'),
      options: employeeSearch.options,
      loading: employeeSearch.loading,
      filterOptions: SERVER_OPTIONS,
      onInputChange: (_event, value, reason) => {
        if (reason === 'input' || reason === 'clear') setEmployeeQuery(value || '');
      },
    },
    {
      key: 'manager',
      label: t('filterRequestManager'),
      options: managerSearch.options,
      loading: managerSearch.loading,
      filterOptions: SERVER_OPTIONS,
      onInputChange: (_event, value, reason) => {
        if (reason === 'input' || reason === 'clear') setManagerQuery(value || '');
      },
    },
  ], [t, tMy, orgUnits, employeeSearch, managerSearch]);

  const columns = useMemo(() => [
    {
      field: 'reference_no',
      headerName: t('colReference'),
      width: 160,
    },
    {
      field: 'title',
      headerName: t('colRequest'),
      flex: 1.2,
      minWidth: 180,
      valueGetter: (_value, row) => displayTitle(tMy, row, tMy),
    },
    {
      field: 'corr_type_code',
      headerName: t('filterRequestType'),
      width: 160,
      valueGetter: (_value, row) => requestTypeLabel(tMy, row),
    },
    {
      field: 'requester_name',
      headerName: t('colEmployee'),
      flex: 1,
      minWidth: 160,
    },
    {
      field: 'org_unit_name',
      headerName: t('colOrgUnit'),
      width: 160,
    },
    {
      field: 'status',
      headerName: t('colStatus'),
      width: 130,
      renderCell: (params) => (
        <Chip
          size="small"
          variant="outlined"
          color={STATUS_COLOR[params.row.status] || 'default'}
          label={codeLabel(tMy, 'status', STATUS_SUFFIX, params.row.status)}
        />
      ),
    },
    {
      field: 'current_step_role',
      headerName: t('colStep'),
      width: 130,
      valueGetter: (_value, row) => codeLabel(tMy, 'role', ROLE_SUFFIX, row.current_step_role),
    },
    {
      field: 'updated_at',
      headerName: t('colUpdated'),
      width: 130,
      valueGetter: (_value, row) => formatDate(row.updated_at || row.created_at, i18n.language),
    },
    {
      field: 'actions',
      headerName: t('colActions'),
      width: 90,
      sortable: false,
      filterable: false,
      renderCell: (params) => {
        const label = t('requestView');
        return (
          <Tooltip title={label}>
            <IconButton
              size="small"
              color="primary"
              aria-label={label}
              onClick={(event) => {
                event.stopPropagation();
                navigate(`/team/${params.row.id}`, { state: { from: 'people-requests' } });
              }}
            >
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      },
    },
  ], [t, tMy, i18n.language, navigate]);

  const rememberChoice = (key, value) => {
    if (key === 'employee') {
      const picked = employeeSearch.options.find((opt) => opt.value === value);
      setEmployeeChoice(value === '' || value == null ? null : (picked || employeeChoice));
    }
    if (key === 'manager') {
      const picked = managerSearch.options.find((opt) => opt.value === value);
      setManagerChoice(value === '' || value == null ? null : (picked || managerChoice));
    }
  };

  return (
    <>
      {error && (
        <Alert
          severity="error"
          sx={{ mx: 1, mt: 1 }}
          onClose={() => setError(null)}
          action={(
            <Button color="inherit" size="small" onClick={() => setReloadToken((n) => n + 1)}>
              {tCommon('retry')}
            </Button>
          )}
        >
          {error}
        </Alert>
      )}
      <FilteredDataGrid
        title={t('requestsAuditTitle')}
        subtitle={t('requestsAuditSubtitle')}
        description={t('requestsAuditDescription')}
        rows={rows}
        columns={columns}
        loading={loading}
        getRowId={(row) => row.id}
        searchValue={searchInput}
        onSearchChange={setSearchInput}
        searchPlaceholder={t('requestsAuditSearch')}
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => {
          rememberChoice(key, value);
          setFilters((prev) => ({ ...prev, [key]: value }));
        }}
        onClearFilters={() => {
          setSearchInput('');
          setSearch('');
          setEmployeeQuery('');
          setManagerQuery('');
          setEmployeeChoice(null);
          setManagerChoice(null);
          setFilters({
            corr_type: '',
            status: '',
            org_unit: '',
            employee: '',
            manager: '',
          });
        }}
        paginationMode="server"
        rowCount={rowCount}
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        pageSize={PAGE_SIZE}
        rowsPerPageOptions={[25, 50, 100]}
        emptyMessage={t('requestsAuditEmpty')}
        emptySubtext={t('requestsAuditEmptyDesc')}
        onRowClick={(params) => setHighlightId(params.row.id)}
        highlightRow={(row) => row.id === highlightId}
        height={560}
      />
    </>
  );
}
