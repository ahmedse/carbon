// src/apps/people/PeopleHome.jsx
// People (Nibras HR & Payroll) — placeholder landing page.
// Minimal entry point registered in App.jsx; the full HRMS modules
// (employees, compliance, payroll) are delivered in later phases.

import React from 'react';
import { Typography } from '@mui/material';
import PeopleIcon from '@mui/icons-material/People';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';

export default function PeopleHome() {
  const { t } = useTranslation('common');
  useDocumentTitle(t('peopleTitle'));

  return (
    <PageContainer>
      <PageHeader
        icon={PeopleIcon}
        title={t('peopleTitle')}
        subtitle={t('peopleSubtitle')}
      />
      <Typography variant="body2" color="text.secondary">
        {t('peopleDescription')}
      </Typography>
    </PageContainer>
  );
}
