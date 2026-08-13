// src/pages/admin/ai/SkillsPanel.jsx
// Route /admin/ai/skills — read-only Skills Catalog panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function SkillsPanel() {
  return (
    <PulseDataPanel
      title="Skills Catalog"
      description="Admitted skills and their admission-gate logs."
      dataKey="skills"
      emptyHint="No skills admitted yet."
    />
  );
}
