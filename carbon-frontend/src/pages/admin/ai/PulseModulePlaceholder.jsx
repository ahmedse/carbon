// src/pages/admin/ai/PulseModulePlaceholder.jsx
// Shared placeholder for gated Pulse panels whose backend ops API (Phase 2)
// has not landed yet. Every /admin/ai/<module> route resolves here until the
// real panel page replaces it in Frontend Phase B.
// RULE_8 tokens only; RULE_16 PageContainer.
import React from 'react';
import { Paper, Stack, Typography } from '@mui/material';
import ConstructionIcon from '@mui/icons-material/Construction';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';

export default function PulseModulePlaceholder({ module }) {
  useDocumentTitle(`${module} — Pulse`);

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
        <Typography variant="h5" fontWeight={700}>{module}</Typography>
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', flex: 1 }}>
          <ConstructionIcon fontSize="large" sx={{ color: 'text.secondary' }} />
          <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
            {module} is not wired yet
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Requires Pulse backend ops API (Phase 2). Not yet wired.
          </Typography>
        </Paper>
      </Stack>
    </PageContainer>
  );
}
