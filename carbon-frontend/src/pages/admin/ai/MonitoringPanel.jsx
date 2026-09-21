// Command → Monitoring — snapshots/insights with Command Center deep link.
import React from 'react';
import { useTranslation } from 'react-i18next';
import PulseDataPanel from './PulseDataPanel';

export default function MonitoringPanel() {
  const { t } = useTranslation('ai');
  return (
    <PulseDataPanel
      title={t('control.monitoring.title')}
      description={t('control.monitoring.description')}
      dataKey="monitoring"
      emptyHint={t('control.monitoring.empty')}
      links={[
        { label: t('control.monitoring.linkCommand'), to: '/admin/ai' },
        { label: t('control.monitoring.linkEvidence'), to: '/admin/ai/evidence?tab=explorer' },
      ]}
    />
  );
}
