// src/pages/admin/ai/MonitoringPanel.jsx
// Route /admin/ai/monitoring — read-only Monitoring panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function MonitoringPanel() {
  return (
    <PulseDataPanel
      title="Monitoring"
      description="System snapshots, notifications, insights, and proactive KG triggers."
      dataKey="monitoring"
      emptyHint="No system snapshots or proactive insights yet."
    />
  );
}
