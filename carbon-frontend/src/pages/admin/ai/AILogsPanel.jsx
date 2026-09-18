// Evidence → Logs — LLM/tool/turn logs with Evidence deep links.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function AILogsPanel() {
  return (
    <PulseDataPanel
      title="AI Logs"
      description="LLM call logs, tool/task executions, turn ledger, and context records. Reconstruct a decision on Evidence."
      dataKey="logs"
      emptyHint="No LLM call logs yet. Run a chat or task to populate."
      links={[
        { label: 'Evidence explorer', to: '/admin/ai/evidence?tab=explorer' },
        { label: 'Audit', to: '/admin/ai/evidence?tab=audit' },
        { label: 'Run timeline', to: '/admin/ai/evidence?tab=runs' },
      ]}
    />
  );
}
