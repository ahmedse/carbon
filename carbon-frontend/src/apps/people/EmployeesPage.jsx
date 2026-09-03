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
  FormControlLabel,
  IconButton,
  MenuItem,
  Snackbar,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import SystemDialog from '../../components/SystemDialog';
import PageContainer from '../../components/layout/PageContainer';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useCompensationAccess } from './useCompensationAccess';
import RevealAmount from './RevealAmount';
import {
  fetchEmployees,
  fetchPositions,
  createEmployee,
} from '../../api/people';
import { fetchOrgUnits } from '../../api/orgUnits';

const EMPTY_FORM = {
  org_unit: '',
  employee_no: '',
  full_name: '',
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

function getInitials(employee) {
  if (employee.name_en_given && employee.name_en_family) {
    return `${employee.name_en_given[0]}${employee.name_en_family[0]}`.toUpperCase();
  }
  const parts = (employee.full_name || '').trim().split(/\s+/);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return (employee.full_name || 'EE').slice(0, 2).toUpperCase();
}

export default function EmployeesPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
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
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

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

  const orgUnitOptions = useMemo(
    () => orgUnits.map((u) => ({ value: String(u.id), label: u.name || u.code || String(u.id) })),
    [orgUnits],
  );
  const rotationOptions = useMemo(() => {
    const set = [...new Set(employees.map((e) => e.rotation).filter(Boolean))];
    return set.map((v) => ({ value: v, label: v }));
  }, [employees]);
  const nationalityOptions = useMemo(() => {
    const set = [...new Set(employees.map((e) => e.nationality).filter(Boolean))];
    return set.map((v) => ({ value: v, label: v }));
  }, [employees]);

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
      if (filters.nationality && emp.nationality !== filters.nationality) return false;
      return true;
    });
  }, [employees, searchValue, filters]);

  const handleView = useCallback((id) => navigate(`/people/employees/${id}`), [navigate]);

  const openCreate = useCallback(() => {
    setForm({ ...EMPTY_FORM });
    setOpenDialog(true);
  }, []);

  const closeDialog = useCallback(() => {
    setOpenDialog(false);
  }, []);

  const handleChange = (event) => {
    const { name, value, checked, type } = event.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSave = async () => {
    if (
      !form.org_unit ||
      !form.employee_no.trim() ||
      !form.full_name.trim() ||
      !form.join_date
    ) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }
    if (canViewCompensation && !String(form.basic_salary).trim()) {
      setSnackbar({ open: true, message: tCommon('allFieldsRequired'), severity: 'error' });
      return;
    }

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
    ];
    for (const [key, val] of optionalText) {
      if (val && String(val).trim()) payload[key] = String(val).trim();
    }
    if (form.position) payload.position = Number(form.position);
    if (form.manager) payload.manager = Number(form.manager);

    setSaving(true);
    try {
      await createEmployee(payload, token);
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
  };

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }));

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

    return [
      { field: 'employee_no', headerName: t('colEmployeeNo'), width: 100 },
      { field: 'full_name', headerName: t('colFullName'), width: 220, renderCell: nameCell },
      { field: 'position', headerName: t('colPosition'), width: 150, valueGetter: (v) => positionMap[v]?.title ?? '—' },
      { field: 'org_unit', headerName: t('colOrgUnit'), width: 150, valueGetter: (v) => orgUnitMap[v]?.name ?? '—' },
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
  }, [t, orgUnitMap, positionMap, handleView]);

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

      <SystemDialog
        open={openDialog}
        title={t('employeeCreateTitle')}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel={tCommon('cancel')}
        actions={
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {tCommon('save')}
          </Button>
        }
      >
        <Stack spacing={2}>
          <TextField
            select
            label={t('formOrgUnit')}
            name="org_unit"
            value={form.org_unit}
            onChange={handleChange}
            fullWidth
            required
          >
            <MenuItem value="" disabled>{t('formOrgUnit')}</MenuItem>
            {orgUnits.map((unit) => (
              <MenuItem key={unit.id} value={unit.id}>{unit.name || unit.code || unit.id}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('formEmployeeNo')}
            name="employee_no"
            value={form.employee_no}
            onChange={handleChange}
            fullWidth
            required
          />
          <TextField
            label={t('colFullName')}
            name="full_name"
            value={form.full_name}
            onChange={handleChange}
            fullWidth
            required
          />
          <TextField
            label={t('formNationality')}
            name="nationality"
            value={form.nationality}
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
          <TextField
            select
            label={t('formGender')}
            name="gender"
            value={form.gender}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="">{t('fieldOptional')}</MenuItem>
            <MenuItem value="male">{t('genderMale')}</MenuItem>
            <MenuItem value="female">{t('genderFemale')}</MenuItem>
          </TextField>
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
          {canViewCompensation && (
            <TextField
              label={t('formBasicSalary')}
              name="basic_salary"
              value={form.basic_salary}
              onChange={handleChange}
              type="number"
              inputProps={{ step: '0.001', min: '0' }}
              fullWidth
              required
            />
          )}
          <TextField
            label={t('formJoinDate')}
            name="join_date"
            value={form.join_date}
            onChange={handleChange}
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
            required
          />
          <TextField
            label={t('formRotation')}
            name="rotation"
            value={form.rotation}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            select
            label={t('colPosition')}
            name="position"
            value={form.position}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="">{t('managerUnassigned')}</MenuItem>
            {positions.map((p) => (
              <MenuItem key={p.id} value={p.id}>{p.title || p.code}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label={t('formManager')}
            name="manager"
            value={form.manager}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="">{t('managerUnassigned')}</MenuItem>
            {employees.map((e) => (
              <MenuItem key={e.id} value={e.id}>{e.employee_no} — {e.full_name}</MenuItem>
            ))}
          </TextField>
          <FormControlLabel
            control={
              <Switch
                checked={form.is_active}
                onChange={handleChange}
                name="is_active"
                color="primary"
              />
            }
            label={t('formIsActive')}
          />
        </Stack>
      </SystemDialog>

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
