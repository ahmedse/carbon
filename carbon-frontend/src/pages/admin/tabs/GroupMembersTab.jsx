// src/pages/admin/tabs/GroupMembersTab.jsx
import React, { useEffect, useState } from 'react';
import { Box, Typography, Table, TableHead, TableRow, TableCell, TableBody, IconButton, Chip, CircularProgress, Alert } from '@mui/material';
import DeleteRounded from '@mui/icons-material/DeleteRounded';
import { useAuth } from '../../../auth/AuthContext';
import { fetchGroupMembers } from '../../../api/groups';
import { deleteScopedRole } from '../../../api/accessControl';

export default function GroupMembersTab({ entityData: group }) {
  const { user } = useAuth();
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchGroupMembers(user?.token, group.id);
        setMembers(Array.isArray(data) ? data : []);
      } catch (err) {
        setError(err.message || 'Failed to load members');
      } finally {
        setLoading(false);
      }
    };
    if (group?.id) load();
  }, [group, user?.token]);

  const handleRemove = async (member) => {
    if (!window.confirm(`Remove ${member.username} from ${group.name}?`)) return;
    try {
      await deleteScopedRole(user?.token, member.scoped_role_id);
      setMembers((prev) => prev.filter((item) => item.id !== member.id));
    } catch (err) {
      setError(err.message || 'Failed to remove member');
    }
  };

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
              <TableCell>Email</TableCell>
              <TableCell>Assigned At</TableCell>
              <TableCell align='right'>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {members.length === 0 ? (
              <TableRow><TableCell colSpan={4}>No global assignments yet.</TableCell></TableRow>
            ) : members.map((member) => (
              <TableRow key={member.id}>
                <TableCell>{member.username}</TableCell>
                <TableCell>{member.email}</TableCell>
                <TableCell>{new Date(member.assigned_at).toLocaleString()}</TableCell>
                <TableCell align='right'>
                  <IconButton size='small' color='error' onClick={() => handleRemove(member)}>
                    <DeleteRounded fontSize='small' />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
}
