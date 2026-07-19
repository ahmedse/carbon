// src/pages/catalog/GovernancePage.jsx
// Governance: Read-only audit log of governance events
import React, { useEffect, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, Table, TableHead, TableRow, TableCell, TableBody,
  CircularProgress, Alert, Chip, Paper, Button
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import AssignmentIcon from '@mui/icons-material/Assignment';
import { fetchGovernanceEvents } from '../../api/catalog';

export default function GovernancePage() {
  const { token } = useAuth();
  const { notify } = useNotification();

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadEvents();
  }, [token]);

  const loadEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchGovernanceEvents(token);
      setEvents(data || []);
      notify({ message: 'Events loaded', type: 'success' });
    } catch (err) {
      const msg = err.message || 'Failed to load governance events';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <AssignmentIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h5" fontWeight={700}>Governance Log</Typography>
            <Typography variant="body2" color="text.secondary">Audit trail of governance events</Typography>
          </Box>
        </Box>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={loadEvents}>
          Refresh
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper>
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: 'action.hover' }}>
              <TableCell fontWeight={600}>Event Type</TableCell>
              <TableCell fontWeight={600}>Asset</TableCell>
              <TableCell fontWeight={600}>Details</TableCell>
              <TableCell fontWeight={600}>Date</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 3 }}>
                  <Typography color="text.secondary">No governance events</Typography>
                </TableCell>
              </TableRow>
            ) : (
              events.map(event => (
                <TableRow key={event.id} hover>
                  <TableCell>
                    <Chip label={event.event_type} size="small" color="primary" variant="outlined" />
                  </TableCell>
                  <TableCell>{event.asset_name || '—'}</TableCell>
                  <TableCell>{event.details || '—'}</TableCell>
                  <TableCell>
                    <Typography variant="caption">
                      {event.created_at ? new Date(event.created_at).toLocaleString() : '—'}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
