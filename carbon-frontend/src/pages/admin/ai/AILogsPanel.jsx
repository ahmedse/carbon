// src/pages/admin/ai/AILogsPanel.jsx
// Route /admin/ai/logs — read-only AI Logs panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function AILogsPanel() {
  return (
    <PulseDataPanel
      title="AI Logs"
      description="LLM call logs, tool / task executions, turn ledger rows, and context records."
      dataKey="logs"
      emptyHint="No LLM call logs yet. Run a chat or task to populate."
    />
  );
}
