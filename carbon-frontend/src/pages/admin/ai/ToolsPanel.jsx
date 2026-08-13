// src/pages/admin/ai/ToolsPanel.jsx
// Route /admin/ai/tools — read-only Tools panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function ToolsPanel() {
  return (
    <PulseDataPanel
      title="Tools"
      description="Tool executions and task executions recorded by the engine."
      dataKey="tools"
      emptyHint="No tool executions recorded yet."
    />
  );
}
