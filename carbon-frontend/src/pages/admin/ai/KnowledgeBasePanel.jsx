// src/pages/admin/ai/KnowledgeBasePanel.jsx
// Route /admin/ai/knowledge — read-only Knowledge Base panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function KnowledgeBasePanel() {
  return (
    <PulseDataPanel
      title="Knowledge Base"
      description="Durable knowledge entities, nodes, edges, and insights recorded by the engine."
      dataKey="knowledge"
      emptyHint="No knowledge entities recorded yet."
    />
  );
}
