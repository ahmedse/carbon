// src/pages/admin/ai/KnowledgeGraphPanel.jsx
// Route /admin/ai/graph — read-only Knowledge Graph panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function KnowledgeGraphPanel() {
  return (
    <PulseDataPanel
      title="Knowledge Graph"
      description="Graph nodes, edges, provenance, query plans, and bootstrap runs."
      dataKey="graph"
      emptyHint="No graph nodes or edges yet. Run schema analysis to bootstrap the graph."
    />
  );
}
