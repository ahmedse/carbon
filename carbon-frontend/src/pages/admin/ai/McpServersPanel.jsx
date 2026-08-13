// src/pages/admin/ai/McpServersPanel.jsx
// Route /admin/ai/mcp — read-only MCP Servers panel.
import React from 'react';
import PulseDataPanel from './PulseDataPanel';

export default function McpServersPanel() {
  return (
    <PulseDataPanel
      title="MCP Servers"
      description="Configured Pulse instances. Connection tokens are never exposed."
      dataKey="mcp"
      emptyHint="No Pulse instances configured."
    />
  );
}
