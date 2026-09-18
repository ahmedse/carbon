// Command → Monitoring — snapshots/insights with Command Center deep link.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function MonitoringPanel() {
  return (
    <PulseDataPanel
      title="Monitoring"
      description="System snapshots, notifications, insights, and proactive KG triggers. Containment and queues live on Command Center."
      dataKey="monitoring"
      emptyHint="No system snapshots or proactive insights yet."
      links={[
        { label: 'Command Center', to: '/admin/ai' },
        { label: 'Evidence explorer', to: '/admin/ai/evidence?tab=explorer' },
      ]}
    />
  );
}
