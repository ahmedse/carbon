// Evidence → Logs — LLM/tool/turn logs with Evidence deep links.
import React from 'react';
import { useTranslation } from 'react-i18next';
import PulseDataPanel from './PulseDataPanel';

export default function AILogsPanel() {
  const { t } = useTranslation('ai');
  return (
    <PulseDataPanel
      title={t('control.logs.title')}
      description={t('control.logs.description')}
      dataKey="logs"
      emptyHint={t('control.logs.empty')}
      links={[
        { label: t('control.logs.linkEvidence'), to: '/admin/ai/evidence?tab=explorer' },
        { label: t('control.logs.linkAudit'), to: '/admin/ai/evidence?tab=audit' },
        { label: t('control.logs.linkRuns'), to: '/admin/ai/evidence?tab=runs' },
      ]}
    />
  );
}
