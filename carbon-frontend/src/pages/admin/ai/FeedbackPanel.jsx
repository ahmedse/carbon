// Learning → Feedback — feedback records with Learning Studio deep links.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function FeedbackPanel() {
  return (
    <PulseDataPanel
      title="Feedback Review"
      description="User and KG feedback / review records. Admission decisions run through Candidates and Review."
      dataKey="feedback"
      emptyHint="No feedback records yet."
      links={[
        { label: 'Learning candidates', to: '/admin/ai/learning?tab=candidates' },
        { label: 'Review queue', to: '/admin/ai/learning?tab=review' },
      ]}
    />
  );
}
