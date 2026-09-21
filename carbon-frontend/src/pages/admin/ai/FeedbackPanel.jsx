// Learning → Feedback — feedback records with Learning Studio deep links.
import React from 'react';
import { useTranslation } from 'react-i18next';
import PulseDataPanel from './PulseDataPanel';

export default function FeedbackPanel() {
  const { t } = useTranslation('ai');
  return (
    <PulseDataPanel
      title={t('control.feedback.title')}
      description={t('control.feedback.description')}
      dataKey="feedback"
      emptyHint={t('control.feedback.empty')}
      links={[
        { label: t('control.feedback.linkCandidates'), to: '/admin/ai/learning?tab=candidates' },
        { label: t('control.feedback.linkReview'), to: '/admin/ai/learning?tab=review' },
      ]}
    />
  );
}
