// src/pages/admin/ai/AgentsPanel.jsx
// Route /admin/ai/agents — read-only Agents panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function AgentsPanel() {
  return (
    <PulseDataPanel
      title="Agents"
      description="Registered agents and their handoff wiring."
      dataKey="agents"
      emptyHint="No agents registered yet."
    />
  );
}
