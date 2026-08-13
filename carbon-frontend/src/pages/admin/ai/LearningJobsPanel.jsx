// src/pages/admin/ai/LearningJobsPanel.jsx
// Route /admin/ai/learning — read-only Learning Jobs panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function LearningJobsPanel() {
  return (
    <PulseDataPanel
      title="Learning Jobs"
      description="Ops runs, trajectories, run steps, and KG quality / recovery records."
      dataKey="learning"
      emptyHint="No learning jobs or runs yet."
    />
  );
}
