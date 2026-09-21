// src/pages/admin/ai/AIWorkspacePage.jsx
// Pulse — embeds the existing Pulse conversation surface.
// Reuses src/shell/AIWorkspace (RULE: reuse, don't refactor). Route /admin/ai/workspace.
import React from 'react';
import { Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { AIWorkspace } from '../../../shell/AIWorkspace';
import { useTranslation } from 'react-i18next';

export default function AIWorkspacePage() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.workspace.title'));
  const navigate = useNavigate();

  return (
    <PageContainer>
      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <AIWorkspace onClose={() => navigate('/admin/ai')} />
      </Box>
    </PageContainer>
  );
}
