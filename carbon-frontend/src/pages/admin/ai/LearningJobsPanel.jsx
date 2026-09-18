// Learning → Jobs — ops/run records with Candidates + Runs deep links.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function LearningJobsPanel() {
  return (
    <PulseDataPanel
      title="Learning Jobs"
      description="Ops runs, trajectories, steps, and KG quality / recovery records. Closed-loop admission is on Candidates."
      dataKey="learning"
      emptyHint="No learning jobs or runs yet."
      links={[
        { label: 'Learning candidates', to: '/admin/ai/learning?tab=candidates' },
        { label: 'Run timeline', to: '/admin/ai/evidence?tab=runs' },
        { label: 'Flywheel', to: '/admin/ai/learning?tab=flywheel' },
      ]}
    />
  );
}
