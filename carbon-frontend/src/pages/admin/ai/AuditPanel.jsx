// src/pages/admin/ai/AuditPanel.jsx
// Route /admin/ai/audit — read-only AI Audit Trail panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function AuditPanel() {
  return (
    <PulseDataPanel
      title="AI Audit Trail"
      description="Actions performed by AI actors across the platform."
      dataKey="audit"
      emptyHint="No AI audit entries yet."
    />
  );
}
