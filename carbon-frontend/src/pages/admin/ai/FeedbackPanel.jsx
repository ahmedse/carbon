// src/pages/admin/ai/FeedbackPanel.jsx
// Route /admin/ai/feedback — read-only Feedback Review panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function FeedbackPanel() {
  return (
    <PulseDataPanel
      title="Feedback Review"
      description="User feedback and knowledge-graph feedback / review records."
      dataKey="feedback"
      emptyHint="No feedback records yet."
    />
  );
}
