// src/shell/AIDomainEntryPoints.jsx
// ONE simple AI button ("Ask AI") that activates the Pulse with the current
// entity's context (table | module). No dropdowns, no per-domain action
// buttons — the context carries what the user is doing (workspace, entity,
// intent) and the Pulse figures out how to help.
import React from 'react';
import { Box, Button } from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { useAITaskTransfer } from './useAITaskTransfer';

// The catalog detail endpoints return the display label as `title` (e.g.
// { id, title, description, ... }), while some list/other shapes use `name`.
function entityLabel(entity, entityId) {
  return entity?.name ?? entity?.title ?? entityId;
}

function buildPayload(entityType, entityId, entity, context) {
  if (entityType === 'table') {
    return {
      table_id: entityId,
      table_name: entityLabel(entity, null),
      row_count: entity?.row_count ?? null,
      module_id: entity?.module_id ?? context?.module_id ?? null,
      module_name: entity?.module_name ?? context?.module_name ?? null,
    };
  }
  return {
    module_id: entityId,
    module_name: entityLabel(entity, null),
  };
}

function sourcePageFor(entityType) {
  return entityType === 'table' ? 'catalog-schema-detail' : 'catalog-data-product-detail';
}

function currentViewFor(entityType) {
  return entityType === 'table' ? 'table_detail' : 'module_detail';
}

export default function AIDomainEntryPoints({ entityType, entityId, entity, context }) {
  const { transferTask } = useAITaskTransfer();

  const handle = () => {
    transferTask(
      'chat',
      buildPayload(entityType, entityId, entity, context),
      {
        title: `Ask about: ${entityLabel(entity, entityId)}`,
        source_page: sourcePageFor(entityType),
        workspaceContext: {
          workspace: 'catalog',
          current_view: currentViewFor(entityType),
          entity_type: entityType,
          entity_id: entityId,
          entity_name: entityLabel(entity, null),
          intent_signal: 'chat',
          recent_actions: [],
        },
      },
    );
  };

  return (
    <Box>
      <Button
        size="small"
        variant="outlined"
        startIcon={<AutoAwesomeIcon />}
        aria-label="Ask AI"
        onClick={handle}
      >
        Ask AI
      </Button>
    </Box>
  );
}
