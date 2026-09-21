// Learning → Jobs — ops/run records with Candidates + Runs deep links.
import React from 'react';
import { useTranslation } from 'react-i18next';
import PulseDataPanel from './PulseDataPanel';

export default function LearningJobsPanel() {
  const { t } = useTranslation('ai');
  return (
    <PulseDataPanel
      title={t('control.learningJobs.title')}
      description={t('control.learningJobs.description')}
      dataKey="learning"
      emptyHint={t('control.learningJobs.empty')}
      links={[
        { label: t('control.learningJobs.linkCandidates'), to: '/admin/ai/learning?tab=candidates' },
        { label: t('control.learningJobs.linkRuns'), to: '/admin/ai/evidence?tab=runs' },
        { label: t('control.learningJobs.linkFlywheel'), to: '/admin/ai/learning?tab=flywheel' },
      ]}
    />
  );
}
