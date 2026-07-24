// src/pages/admin/tabs/GroupScopedAssignmentsTab.jsx
import React, { useEffect, useState } from 'react';
import { Box, Typography, Table, TableHead, TableRow, TableCell, TableBody, Chip, CircularProgress, Alert } from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { fetchGroupScopedAssignments } from '../../../api/groups';

export default function GroupScopedAssignmentsTab({ entityData: group }) {
  const { user } = useAuth();
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchGroupScopedAssignments(user?.token, group.id);
        setAssignments(Array.isArray(data) ? data : []);
      } catch (err) {
        setError(err.message || 'Failed to load scoped assignments');
      } finally {
        setLoading(false);
      }
    };
    if (group?.id) load();
  }, [group, user?.token]);

  return (
    <Box sx={{ p: 3 }}>
      {error && <Alert severity='error' sx={{ mb: 2 }}>{error}</Alert>}
      {loading ? (
        <Box sx={{ textAlign: 'center', py: 6 }}><CircularProgress /></Box>
      ) : (
        <Table size='small'>
          <TableHead>
            <TableRow>
              <TableCell>User</TableCell>
              <TableCell>Org Unit</TableCell>
              <TableCell>Module</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Assigned At</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {assignments.length === 0 ? (
              <TableRow><TableCell colSpan={5}>No scoped assignments yet.</TableCell></TableRow>
            ) : assignments.map((assignment) => (
              <TableRow key={assignment.id}>
                <TableCell>{assignment.user}</TableCell>
                <TableCell>{assignment.org_unit || '—'}</TableCell>
                <TableCell>{assignment.module || '—'}</TableCell>
                <TableCell>
                  <Chip size='small' label={assignment.is_active ? 'Active' : 'Inactive'} color={assignment.is_active ? 'success' : 'default'} />
                </TableCell>
                <TableCell>{new Date(assignment.created_at).toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
}
