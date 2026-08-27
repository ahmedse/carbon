// src/inspector/tabs/helpers.jsx
// Shared builders for contextual inspector tabs (ADR-0019 Phase C).
//
// These wrap existing detail-page metrics components so each entity type can
// contribute its summary/audit content to the global drawer without
// re-implementing the panel chrome. The wrapped component is rendered with the
// same props the legacy metrics panels received:
//   `entityData`  -> payload.entityData
//   `additionalProps` -> every other payload key
//
// Also provides `registerCollectionSummaryTab` for collection pages
// (Data Sources / Exports / Imports) that expose a flat list of summary cards.

import React from 'react';
import { Box, Typography } from '@mui/material';
import { registerInspectorTab } from '../InspectorTabRegistry';

/**
 * Register a single tab that renders an existing `{ entityData, additionalProps }`
 * metrics component. Returns an unregister function (use as effect cleanup).
 */
export function registerEntityInspectorTab(props) {
  const { id, entityType, label, icon, order = 10, Component } = props;
  return registerInspectorTab({
    id,
    label,
    icon,
    order,
    matches: (ctx) => ctx?.entityType === entityType,
    render: (ctx) => {
      const payload = ctx?.payload || {};
      const { entityData, ...additionalProps } = payload;
      return <Component entityData={entityData} additionalProps={additionalProps} />;
    },
  });
}

/* ── Summary cards renderer (collection pages) ───────────────────────────── */

function SummaryCards({ cards = [] }) {
  if (!cards?.length) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">No summary available.</Typography>
      </Box>
    );
  }
  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
      {cards.map((card) => (
        <Box
          key={card.title}
          sx={{
            p: 1.5,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
          }}
        >
          <Typography variant="body2" color="text.secondary">{card.title}</Typography>
          <Typography variant="body2" fontWeight={700}>{card.value}</Typography>
        </Box>
      ))}
    </Box>
  );
}

/**
 * Register a "Summary" tab for a collection entity type. The page supplies
 * `payload.summaryCards` (array of `{ title, value }`).
 */
export function registerCollectionSummaryTab({
  id,
  entityType,
  label = 'Summary',
  order = 10,
}) {
  return registerInspectorTab({
    id,
    label,
    order,
    matches: (ctx) => ctx?.entityType === entityType,
    render: (ctx) => <SummaryCards cards={ctx?.payload?.summaryCards || []} />,
  });
}
