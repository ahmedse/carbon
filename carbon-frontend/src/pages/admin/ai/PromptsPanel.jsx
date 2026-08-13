// src/pages/admin/ai/PromptsPanel.jsx
// Route /admin/ai/prompts — read-only Prompts & Playbook panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function PromptsPanel() {
  return (
    <PulseDataPanel
      title="Prompts & Playbook"
      description="Prompt versions, prompt evaluations, and playbook blocks."
      dataKey="prompts"
      emptyHint="No prompt versions or playbook blocks yet."
    />
  );
}
