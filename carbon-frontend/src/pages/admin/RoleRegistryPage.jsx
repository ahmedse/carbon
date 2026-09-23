import React, { useEffect, useMemo, useState } from 'react';
import {
  Box, Typography, Alert, Accordion, AccordionSummary, AccordionDetails,
  Table, TableHead, TableRow, TableCell, TableBody, Chip,
} from '@mui/material';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { useAuth } from '../../auth/AuthContext';
import { apiFetch } from '../../api/api';

export default function RoleRegistryPage() {
  useDocumentTitle("Role Registry");
  const { user } = useAuth();
  const token = user?.token;
  const [apps, setApps] = useState([]);
  const [duties, setDuties] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [error, setError] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [filters, setFilters] = useState({ domain: '' });

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiFetch('accounts/role-registry/', { method: 'GET', token });
        setApps(Array.isArray(data.apps) ? data.apps : []);
        setDuties(Array.isArray(data.duties) ? data.duties : []);
        setConflicts(Array.isArray(data.conflicts) ? data.conflicts : []);
      } catch (e) {
        setError(e.message || 'Failed to load role registry');
      }
    };

    if (token) load();
  }, [token]);

  const domains = [...new Set(duties.map((d) => d.domain))];
  const filterDefs = useMemo(() => [
    {
      key: 'domain',
      label: 'Domain',
      emptyLabel: 'All domains',
      options: domains.map((domain) => ({ value: domain, label: domain })),
    },
  ], [domains]);
  const filteredDuties = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return duties.filter((duty) => {
      if (filters.domain && duty.domain !== filters.domain) return false;
      if (!q) return true;
      return [duty.duty, duty.group, ...(duty.capabilities || [])].join(' ').toLowerCase().includes(q);
    });
  }, [duties, searchValue, filters]);
  const dutyColumns = useMemo(() => [
    { field: 'duty', headerName: 'Duty', flex: 1, minWidth: 180 },
    { field: 'group', headerName: 'Stored group', flex: 1, minWidth: 180 },
    { field: 'domain', headerName: 'Domain', width: 140 },
    {
      field: 'capabilities',
      headerName: 'Capabilities',
      flex: 1.4,
      minWidth: 220,
      valueGetter: (value, row) => (row.capabilities || []).join(', ') || '—',
    },
  ], []);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h5' fontWeight={700} gutterBottom>Role Registry</Typography>
      <Alert severity='info' sx={{ mb: 3 }}>
        The duty catalog is what grants access. Assignments and position profiles use these ids.
        App manifest roles below are declarations. A manifest key grants nothing until it is the same id as a duty.
      </Alert>
      {conflicts.length > 0 && (
        <Alert severity='warning' sx={{ mb: 2 }}>
          Separation of duties: {conflicts.map((pair) => pair.join(' × ')).join('; ')}.
        </Alert>
      )}
      {error && <Alert severity='error' sx={{ mb: 2 }}>{error}</Alert>}

      <FilteredDataGrid
        embedded
        title="Duty catalog"
        rows={filteredDuties}
        columns={dutyColumns}
        getRowId={(row) => row.duty}
        countLabel={`${filteredDuties.length} of ${duties.length} duties`}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder="Search duty, group, capability…"
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => { setSearchValue(''); setFilters({ domain: '' }); }}
        emptyMessage="No duties match."
        height={420}
      />

      <Typography variant='h6' sx={{ mt: 3 }} gutterBottom>App manifest roles</Typography>
      {apps.map((app) => (
        <Accordion key={app.id}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
              <Typography variant='h6'>{app.name}</Typography>
              <Chip label={`${app.roles?.length || 0} roles`} size='small' />
              <Typography variant='caption' color='text.secondary' sx={{ ml: 'auto' }}>v{app.version}</Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>Manifest key</TableCell>
                  <TableCell>Label</TableCell>
                  <TableCell align='center'>Scoped</TableCell>
                  <TableCell>Description</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(app.roles || []).map((role) => (
                  <TableRow key={role.key}>
                    <TableCell><Typography variant='body2' fontFamily='monospace'>{role.key}</Typography></TableCell>
                    <TableCell>{role.label}</TableCell>
                    <TableCell align='center'>{role.scoped ? <CheckCircleIcon color='success' fontSize='small' /> : <CancelIcon color='disabled' fontSize='small' />}</TableCell>
                    <TableCell>{role.description}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AccordionDetails>
        </Accordion>
      ))}
      {apps.length === 0 && duties.length === 0 && !error && <Alert severity='warning'>No role data was returned.</Alert>}
    </Box>
  );
}
