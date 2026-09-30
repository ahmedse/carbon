import React, { useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import SchoolIcon from '@mui/icons-material/School';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import AppEnabledRoute from '../../components/AppEnabledRoute';
import GuideHub from '../../components/guide/GuideHub';

/** /guide/:appId and /guide/:appId/:lessonId. The same page serves every domain app that ships a guide pack. */
export default function GuidePage() {
  const { t } = useTranslation('guide');
  const { appId, lessonId } = useParams();
  const navigate = useNavigate();
  useDocumentTitle(t('hub.title'));
  const onOpen = useCallback((id, opts) => {
    navigate(`/guide/${appId}/${id}`, { replace: Boolean(opts && opts.replace) });
  }, [navigate, appId]);
  const onClose = useCallback(() => navigate(`/guide/${appId}?list=1`), [navigate, appId]);

  return (
    <AppEnabledRoute appId={appId}>
      <PageContainer>
        <PageHeader
          icon={SchoolIcon}
          title={t('hub.title')}
          titleComponent="h1"
          subtitle={t('hub.subtitle')}
          description={t('hub.description')}
        />
        <GuideHub
          appId={appId}
          lessonId={lessonId}
          onOpen={onOpen}
          onClose={onClose}
        />
      </PageContainer>
    </AppEnabledRoute>
  );
}
