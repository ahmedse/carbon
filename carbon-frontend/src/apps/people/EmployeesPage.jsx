// src/apps/people/EmployeesPage.jsx
// People & Payroll — Employees (thick page).
// Standard DataGrid shell (search + collapsible filters), progressive
// compensation disclosure (Tier-2), and governed lifecycle ops: deactivation
// requires a reason + effective date and records chronicle + governance audit
// events on the server — it is NOT a bare DELETE.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Snackbar,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckIcon from '@mui/icons-material/Check';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import EditIcon from '@mui/icons-material/Edit';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import PageContainer from '../../components/layout/PageContainer';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmployeeWizard from './EmployeeWizard';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useReferenceOptions } from '../../hooks/useReferenceOptions';
import { useAuth } from '../../auth/AuthContext';
import { useCompensationAccess } from './useCompensationAccess';
import RevealAmount from './RevealAmount';
import { formatDate } from './utils';
import {
  fetchEmployees,
  fetchPositions,
  createEmployee,
  updateEmployee,
} from '../../api/people';
import { fetchOrgUnits } from '../../api/orgUnits';

function getInitials(employee) {
  if (employee.name_en_given && employee.name_en_family) {
    return `${employee.name_en_given[0]}${employee.name_en_family[0]}`.toUpperCase();
  }
  const parts = (employee.full_name || '').trim().split(/\s+/);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return (employee.full_name || 'EE').slice(0, 2).toUpperCase();
}

function labelMapFromOptions(options) {
  const map = {};
  for (const o of options || []) map[o.value] = o.label;
  return map;
}

function CopyRow({ label, value, copied, onCopy }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, p: 1, borderRadius: 1, bgcolor: 'action.hover' }}>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, wordBreak: 'break-all' }}>
          {value}
        </Typography>
      </Box>
      <IconButton size="small" onClick={onCopy} color={copied ? 'success' : 'primary'}>
        {copied ? <CheckIcon sx={{ fontSize: 16 }} /> : <ContentCopyIcon sx={{ fontSize: 16 }} />}
      </IconButton>
    </Box>
  );
}

export default function EmployeesPage() {
  const { t } = useTranslation('people');
  useDocumentTitle(t('employeesTitle'));
  const { token } = useAuth();
  const { canViewCompensation } = useCompensationAccess();
  const navigate = useNavigate();

  const [employees, setEmployees] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({
    status: '',
    org_unit: '',
    rotation: '',
    kuwaitization: '',
    nationality: '',
  });

  const [openDialog, setOpenDialog] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [saving, setSaving] = useState(false);

  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [createdAccount, setCreatedAccount] = useState(null);
  const [copiedField, setCopiedField] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [employeesData, orgUnitsData, positionsData] = await Promise.all([
        fetchEmployees(token),
        fetchOrgUnits(token),
        fetchPositions(token),
      ]);
      setEmployees(Array.isArray(employeesData) ? employeesData : employeesData?.results || []);
      setOrgUnits(Array.isArray(orgUnitsData) ? orgUnitsData : []);
      setPositions(Array.isArray(positionsData) ? positionsData : positionsData?.results || []);
    } catch (err) {
      setError(err?.message || err?.feedback?.title || t('employeesLoadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const orgUnitMap = useMemo(() => {
    const map = {};
    for (const u of orgUnits) if (u?.id != null) map[u.id] = u;
    return map;
  }, [orgUnits]);

  const positionMap = useMemo(() => {
    const map = {};
    for (const p of positions) if (p?.id != null) map[p.id] = p;
    return map;
  }, [positions]);

  const employeeMap = useMemo(() => {
    const map = {};
    for (const e of employees) if (e?.id != null) map[e.id] = e;
    return map;
  }, [employees]);

  const orgUnitOptions = useMemo(
    () => orgUnits.map((u) => ({ value: String(u.id), label: u.name || u.code || String(u.id) })),
    [orgUnits],
  );
  const rotationRef = useReferenceOptions('rotation_pattern');
  const nationalityRef = useReferenceOptions('nationality');
  const genderRef = useReferenceOptions('gender');
  const employmentTypeRef = useReferenceOptions('employment_type');
  const contractTypeRef = useReferenceOptions('contract_type');
  const rotationOptions = rotationRef.options;
  const nationalityOptions = nationalityRef.options;

  const genderMap = useMemo(() => labelMapFromOptions(genderRef.options), [genderRef.options]);
  const employmentTypeMap = useMemo(() => labelMapFromOptions(employmentTypeRef.options), [employmentTypeRef.options]);
  const contractTypeMap = useMemo(() => labelMapFromOptions(contractTypeRef.options), [contractTypeRef.options]);

  const filterDefs = useMemo(() => [
    {
      key: 'status',
      label: t('filterStatus'),
      emptyLabel: t('filterAll'),
      options: [
        { value: 'active', label: t('statusActive') },
        { value: 'inactive', label: t('statusInactive') },
      ],
    },
    { key: 'org_unit', label: t('colOrgUnit'), emptyLabel: t('filterAll'), options: orgUnitOptions },
    { key: 'rotation', label: t('colRotation'), emptyLabel: t('filterAll'), options: rotationOptions },
    {
      key: 'kuwaitization',
      label: t('colKuwaitization'),
      emptyLabel: t('filterAll'),
      options: [
        { value: 'true', label: t('yes') },
        { value: 'false', label: t('no') },
      ],
    },
    { key: 'nationality', label: t('colNationality'), emptyLabel: t('filterAll'), options: nationalityOptions },
  ], [t, orgUnitOptions, rotationOptions, nationalityOptions]);

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return employees.filter((emp) => {
      if (q) {
        const hay = `${emp.employee_no ?? ''} ${emp.full_name ?? ''} ${emp.nationality ?? ''} ${emp.civil_id ?? ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (filters.status === 'active' && !emp.is_active) return false;
      if (filters.status === 'inactive' && emp.is_active) return false;
      if (filters.org_unit && String(emp.org_unit) !== String(filters.org_unit)) return false;
      if (filters.rotation && emp.rotation !== filters.rotation) return false;
      if (filters.kuwaitization === 'true' && !emp.kuwaitization) return false;
      if (filters.kuwaitization === 'false' && emp.kuwaitization) return false;
      if (filters.nationality) {
        const nat = nationalityOptions.find((o) => o.value === filters.nationality);
        const matches = emp.nationality_code === filters.nationality
          || (nat && emp.nationality === nat.label);
        if (!matches) return false;
      }
      return true;
    });
  }, [employees, searchValue, filters, nationalityOptions]);

  const handleView = useCallback((id) => navigate(`/people/employees/${id}`), [navigate]);

  const openCreate = useCallback(() => {
    setEditingEmployee(null);
    setOpenDialog(true);
  }, []);

  const openEdit = useCallback((employee) => {
    setEditingEmployee(employee);
    setOpenDialog(true);
  }, []);

  const closeDialog = useCallback(() => {
    setOpenDialog(false);
  }, []);

  const handleSaveWizard = useCallback(async (payload) => {
    setSaving(true);
    try {
      if (editingEmployee) {
        await updateEmployee(editingEmployee.id, payload, token);
      } else {
        const created = await createEmployee(payload, token);
        setCreatedAccount({
          username: created?.username || null,
          initialPassword: created?.initial_password || null,
        });
      }
      closeDialog();
      setSnackbar({ open: true, message: t('employeeSaved'), severity: 'success' });
      await loadData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err?.message || err?.feedback?.title || err?.detail || t('actionError'),
        severity: 'error',
      });
    } finally {
      setSaving(false);
    }
  }, [token, t, loadData, closeDialog, editingEmployee]);

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

  const copyToClipboard = useCallback(async (text, field) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard may be unavailable (e.g. non-HTTPS); value is still shown.
    }
    setCopiedField(field);
    window.setTimeout(() => setCopiedField(null), 1500);
  }, []);

  const columns = useMemo(() => {
    const nameCell = (params) => (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Avatar sx={{ width: 24, height: 24, fontSize: '0.6rem', bgcolor: 'primary.main' }}>
          {getInitials(params.row)}
        </Avatar>
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: '0.7rem', fontWeight: 600, lineHeight: 1.2 }}>
            {params.row.full_name ?? '—'}
          </Typography>
          {params.row.name_ar_given || params.row.name_ar_family ? (
            <Typography noWrap sx={{ fontSize: '0.58rem', color: 'text.disabled', lineHeight: 1.2 }}>
              {`${params.row.name_ar_given || ''} ${params.row.name_ar_family || ''}`.trim()}
            </Typography>
          ) : null}
        </Box>
      </Box>
    );

    const managerName = (v) => {
      const m = employeeMap[v];
      return m ? `${m.employee_no} — ${m.full_name}` : '—';
    };
    const refLabel = (map, v) => (v && map[v]) || v || '—';

    return [
      { field: 'employee_no', headerName: t('colEmployeeNo'), width: 100 },
      { field: 'full_name', headerName: t('colFullName'), width: 200, renderCell: nameCell },
      {
        field: 'username',
        headerName: t('colUsername'),
        width: 130,
        renderCell: (p) => (p.row.username
          ? <Chip size="small" color="info" variant="outlined" label={p.row.username} />
          : <Typography variant="body2" color="text.disabled">{t('colUserUnlinked')}</Typography>),
      },
      { field: 'civil_id', headerName: t('colCivilId'), width: 120, valueGetter: (v) => v || '—' },
      { field: 'gender', headerName: t('colGender'), width: 90, valueGetter: (v) => refLabel(genderMap, v) },
      { field: 'date_of_birth', headerName: t('colDateOfBirth'), width: 110, valueGetter: (v) => formatDate(v) },
      { field: 'join_date', headerName: t('colJoinDate'), width: 110, valueGetter: (v) => formatDate(v) },
      { field: 'position', headerName: t('colPosition'), width: 140, valueGetter: (v) => positionMap[v]?.title ?? '—' },
      { field: 'org_unit', headerName: t('colOrgUnit'), width: 140, valueGetter: (v) => orgUnitMap[v]?.name ?? '—' },
      { field: 'manager', headerName: t('colManager'), width: 160, valueGetter: (v) => managerName(v) },
      { field: 'employment_type_code', headerName: t('colEmploymentType'), width: 130, valueGetter: (v) => refLabel(employmentTypeMap, v) },
      { field: 'contract_type_code', headerName: t('colContractType'), width: 130, valueGetter: (v) => refLabel(contractTypeMap, v) },
      { field: 'nationality', headerName: t('colNationality'), width: 100, valueGetter: (v) => v || '—' },
      {
        field: 'rotation',
        headerName: t('colRotation'),
        width: 90,
        renderCell: (p) => (p.value
          ? <Chip size="small" variant="outlined" label={p.value} />
          : <Typography variant="body2" color="text.disabled">—</Typography>),
      },
      {
        field: 'kuwaitization',
        headerName: t('colKuwaitization'),
        width: 110,
        renderCell: (p) => (p.value
          ? <Chip size="small" color="primary" variant="outlined" label={t('yes')} />
          : <Chip size="small" variant="outlined" label={t('no')} />),
      },
      {
        field: 'compensation',
        headerName: t('colCompensation'),
        width: 150,
        sortable: false,
        valueGetter: () => null,
        renderCell: (p) => <RevealAmount employeeId={p.row.id} />,
      },
      {
        field: 'is_active',
        headerName: t('colStatus'),
        width: 90,
        renderCell: (p) => (
          <Chip
            size="small"
            color={p.value ? 'success' : 'default'}
            label={p.value ? t('statusActive') : t('statusInactive')}
          />
        ),
      },
      {
        field: 'actions',
        headerName: t('colActions'),
        width: 70,
        sortable: false,
        filterable: false,
        renderCell: (p) => {
          const emp = p.row;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
              <Tooltip title={t('actionEditEmployee')}>
                <IconButton size="small" onClick={() => openEdit(emp)} sx={{ color: 'primary.main' }}>
                  <EditIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
              <Tooltip title={t('actionViewEmployee')}>
                <IconButton size="small" onClick={() => handleView(emp.id)} sx={{ color: 'primary.main' }}>
                  <VisibilityIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            </Box>
          );
        },
      },
    ];
  }, [t, orgUnitMap, positionMap, employeeMap, genderMap, employmentTypeMap, contractTypeMap, handleView, openEdit]);

  if (error) {
    return (
      <PageContainer>
        <ErrorAlert message={error} onRetry={loadData} />
      </PageContainer>
    );
  }

  return (
    <>
      <FilteredDataGrid
        title={t('employeesTitle')}
        subtitle={t('employeesSubtitle')}
        description={t('employeesDescription')}
        actions={
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={openCreate}>
            {t('actionAddEmployee')}
          </Button>
        }
        rows={filteredRows}
        columns={columns}
        loading={loading}
        countLabel={t('employeesCount', { count: filteredRows.length, total: employees.length })}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => {
          setSearchValue('');
          setFilters({ status: '', org_unit: '', rotation: '', kuwaitization: '', nationality: '' });
        }}
        emptyMessage={t('employeesEmpty')}
        emptySubtext={t('employeesEmptyDesc')}
      />

      <Dialog
        open={openDialog}
        onClose={(event, reason) => {
          if (reason === 'backdropClick' || reason === 'escapeKeyDown') return;
          closeDialog();
        }}
        disableEscapeKeyDown
        fullWidth
        maxWidth="lg"
      >
        <DialogTitle sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          {editingEmployee ? t('employeeEditTitle') : t('employeeCreateTitle')}
          {editingEmployee?.username ? (
            <Typography variant="caption" color="text.secondary">
              {t('colUsername')}: {editingEmployee.username}
            </Typography>
          ) : null}
        </DialogTitle>
        <DialogContent sx={{ height: '70vh', minHeight: 480, p: 2 }}>
          <EmployeeWizard
            key={editingEmployee?.id ?? 'new'}
            employee={editingEmployee}
            orgUnits={orgUnits}
            positions={positions}
            employees={employees}
            canViewCompensation={canViewCompensation}
            saving={saving}
            onSave={handleSaveWizard}
            onCancel={closeDialog}
          />
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(createdAccount)}
        onClose={() => setCreatedAccount(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t('employeeCreatedTitle')}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            {t('provisionAccountNote')}
          </Typography>
          <Stack spacing={1}>
            <CopyRow
              label={t('colUsername')}
              value={createdAccount?.username}
              copied={copiedField === 'username'}
              onCopy={() => copyToClipboard(createdAccount?.username, 'username')}
            />
            {createdAccount?.initialPassword ? (
              <CopyRow
                label={t('provisionPassword')}
                value={createdAccount.initialPassword}
                copied={copiedField === 'password'}
                onCopy={() => copyToClipboard(createdAccount.initialPassword, 'password')}
              />
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreatedAccount(null)}>{t('close')}</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
}
