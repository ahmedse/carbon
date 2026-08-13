// src/pages/admin/ai/MemoryPanel.jsx
// Route /admin/ai/memory — read-only Memory panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function MemoryPanel() {
  return (
    <PulseDataPanel
      title="Memory"
      description="Long-term and episodic memory rows written by the engine."
      dataKey="memory"
      emptyHint="No memory rows recorded yet."
    />
  );
}
