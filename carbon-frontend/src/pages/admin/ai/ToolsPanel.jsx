// Domain → Tools — tool/task executions with Evidence deep links (ADR-0036).
import React from 'react';
import { useTranslation } from 'react-i18next';
import PulseDataPanel from './PulseDataPanel';

export default function ToolsPanel() {
  const { t } = useTranslation('ai');
  return (
    <PulseDataPanel
      title={t('control.tools.title')}
      description={t('control.tools.description')}
      dataKey="tools"
      emptyHint={t('control.tools.empty')}
      links={[
        { label: t('control.tools.linkEvidence'), to: '/admin/ai/evidence?tab=explorer' },
        { label: t('control.tools.linkRuns'), to: '/admin/ai/evidence?tab=runs' },
      ]}
    />
  );
}
