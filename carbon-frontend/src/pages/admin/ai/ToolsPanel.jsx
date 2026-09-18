// Domain → Tools — tool/task executions with Evidence deep links (ADR-0036).
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function ToolsPanel() {
  return (
    <PulseDataPanel
      title="Tools"
      description="Tool and task executions recorded by the engine. For a single run’s full trail, open Evidence."
      dataKey="tools"
      emptyHint="No tool executions recorded yet."
      links={[
        { label: 'Evidence explorer', to: '/admin/ai/evidence?tab=explorer' },
        { label: 'Run timeline', to: '/admin/ai/evidence?tab=runs' },
      ]}
    />
  );
}
