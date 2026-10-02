import React, { useCallback } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import SchoolIcon from '@mui/icons-material/School';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import AppEnabledRoute from '../../components/AppEnabledRoute';
import GuideHub from '../../components/guide/GuideHub';

/**
 * /guide/:appId and /guide/:appId/:lessonId.
 *
 * Generic for every domain app that ships a guide pack — but Carbon's standalone
 * hub UI is retired: Journey is the single teaching surface, so /guide/carbon and
 * /guide/carbon/<lessonId> (the load-bearing /guide/carbon/D2 alias included)
 * redirect to the Journey station page or lesson reader. The lesson id is never
 * renamed, so an old bookmark resolves the same lesson. Other apps keep the hub.
 */
export default function GuidePage() {
  const { t } = useTranslation('guide');
  const { appId, lessonId } = useParams();
  const navigate = useNavigate();
  useDocumentTitle(t('hub.title'));
  const onOpen = useCallback((id, opts) => {
    navigate(`/guide/${appId}/${id}`, { replace: Boolean(opts && opts.replace) });
  }, [navigate, appId]);
  const onClose = useCallback(() => navigate(`/guide/${appId}?list=1`), [navigate, appId]);

  const journeyTarget = lessonId ? `/journey/${appId}/${lessonId}` : `/journey/${appId}`;

  return (
    <AppEnabledRoute appId={appId}>
      {appId === 'carbon' ? (
        <Navigate to={journeyTarget} replace />
      ) : (
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
      )}
    </AppEnabledRoute>
  );
}
