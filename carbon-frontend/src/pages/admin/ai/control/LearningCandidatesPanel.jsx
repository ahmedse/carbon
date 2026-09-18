// src/pages/admin/ai/control/LearningCandidatesPanel.jsx
import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  Link,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { getLearningCandidates } from '../../../../api/aiControlPlane';

export default function LearningCandidatesPanel() {
  useDocumentTitle('Learning Candidates');
  const { token } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getLearningCandidates(token, { limit: 100 });
      setRows(data?.results || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Typography variant="h5" fontWeight={700}>
          Candidates
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Unified queue: process reviews, pending skills, learning outcomes, DQ feedback.
          Nothing here is authoritative until admitted.
        </Typography>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        ) : (
          <Stack spacing={1}>
            {rows.map((row) => (
              <Paper key={`${row.kind}-${row.id}`} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                  <Chip size="small" label={row.kind} />
                  <Typography variant="body2" fontWeight={600} sx={{ flex: 1 }}>
                    {row.title}
                  </Typography>
                  <Chip size="small" variant="outlined" label={row.status || '—'} />
                  {row.href && (
                    <Link component={RouterLink} to={row.href} variant="body2">
                      Open
                    </Link>
                  )}
                </Stack>
              </Paper>
            ))}
            {!rows.length && (
              <Typography variant="body2" color="text.secondary">
                No open candidates.
              </Typography>
            )}
          </Stack>
        )}
      </Stack>
    </PageContainer>
  );
}
