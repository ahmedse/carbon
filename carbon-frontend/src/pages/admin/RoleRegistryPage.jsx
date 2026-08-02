import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Alert, Accordion, AccordionSummary, AccordionDetails,
  Table, TableHead, TableRow, TableCell, TableBody, Chip,
} from '@mui/material';
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
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiFetch('accounts/role-registry/', { method: 'GET', token }); // apiFetch returns parsed JSON
        setApps(Array.isArray(data.apps) ? data.apps : []);
      } catch (e) {
        setError(e.message || 'Failed to load role registry');
      }
    };

    if (token) load();
  }, [token]);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h5' fontWeight={700} gutterBottom>Role Registry</Typography>
      <Alert severity='info' sx={{ mb: 3 }}>
        This registry reflects the roles declared by each app manifest and is used to drive platform and app-level access.
      </Alert>
      {error && <Alert severity='error' sx={{ mb: 2 }}>{error}</Alert>}
      {apps.map((app) => (
        <Accordion key={app.id} defaultExpanded={app.id === 'carbon'}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
              <Typography variant='h6'>{app.name}</Typography>
              <Chip label={`${app.roles?.length || 0} roles`} size='small' color='primary' />
              <Typography variant='caption' color='text.secondary' sx={{ ml: 'auto' }}>v{app.version}</Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>Role Key</TableCell>
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
      {apps.length === 0 && !error && <Alert severity='warning'>No role data was returned.</Alert>}
    </Box>
  );
}
