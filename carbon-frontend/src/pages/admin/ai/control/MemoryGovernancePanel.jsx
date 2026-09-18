// src/pages/admin/ai/control/MemoryGovernancePanel.jsx
// ADR-0036 Phase 4 — memory revoke (soft) + forget (hard) for Assets.
import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import useDocumentTitle from '../../../../hooks/useDocumentTitle';
import PageContainer from '../../../../components/layout/PageContainer';
import { useAuth } from '../../../../auth/AuthContext';
import { useNotification } from '../../../../components/NotificationProvider';
import {
  forgetFact,
  listFacts,
  revokeMemoryFact,
} from '../../../../api/aiWorkspace';

export default function MemoryGovernancePanel() {
  useDocumentTitle('Memory Assets');
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const [facts, setFacts] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listFacts(token, { limit: 100 });
      setFacts(data?.results || []);
    } catch {
      setFacts([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onRevoke = async (id) => {
    try {
      await revokeMemoryFact(token, id, 'steward revoke from Assets');
      notify({ message: 'Memory revoked (kept for provenance).', type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Revoke failed');
    }
  };

  const onForget = async (id) => {
    try {
      await forgetFact(token, id);
      notify({ message: 'Memory forgotten (hard delete).', type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Forget failed');
    }
  };

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Typography variant="h5" fontWeight={700}>
          Memory
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Revoke stops future use while keeping the row for audit. Forget is hard delete (GDPR).
        </Typography>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        ) : (
          <Stack spacing={1}>
            {facts.map((fact) => (
              <Paper key={fact.id} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="flex-start">
                  <Stack spacing={0.5} sx={{ flex: 1, minWidth: 0 }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip size="small" label={fact.category || 'fact'} />
                      <Typography variant="caption" color="text.secondary">
                        conf {fact.confidence ?? '—'}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>
                      {fact.content}
                    </Typography>
                  </Stack>
                  <Button size="small" onClick={() => onRevoke(fact.id)}>
                    Revoke
                  </Button>
                  <Button size="small" color="error" onClick={() => onForget(fact.id)}>
                    Forget
                  </Button>
                </Stack>
              </Paper>
            ))}
            {!facts.length && (
              <Typography variant="body2" color="text.secondary">
                No memory facts.
              </Typography>
            )}
          </Stack>
        )}
      </Stack>
    </PageContainer>
  );
}
