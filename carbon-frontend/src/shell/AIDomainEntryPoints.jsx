// src/shell/AIDomainEntryPoints.jsx
// Renders a domain app's manifest `entry_points` as compact outlined buttons
// scoped to an entity (table | module). Dispatches via useAITaskTransfer.
import React from 'react';
import { Box, Button } from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import DescriptionIcon from '@mui/icons-material/Description';
import ChatIcon from '@mui/icons-material/Chat';
import { useAuth } from '../auth/AuthContext';
import { useDomainManifests } from '../hooks/useDomainManifests';
import { useAITaskTransfer } from './useAITaskTransfer';

const ICON_MAP = {
  FactCheck: FactCheckIcon,
  AutoFixHigh: AutoFixHighIcon,
  ManageSearch: ManageSearchIcon,
  Description: DescriptionIcon,
  Chat: ChatIcon,
};

function buildPayload(entityType, entityId, entity, context) {
  if (entityType === 'table') {
    return {
      table_id: entityId,
      table_name: entity?.name ?? null,
      row_count: entity?.row_count ?? null,
      module_id: entity?.module_id ?? context?.module_id ?? null,
      module_name: context?.module_name ?? null,
    };
  }
  return {
    module_id: entityId,
    module_name: entity?.name ?? null,
  };
}

export default function AIDomainEntryPoints({ entityType, entityId, entity, context }) {
  const { token } = useAuth();
  const { manifests } = useDomainManifests(token);
  const { transferTask } = useAITaskTransfer();

  const points = [];
  for (const manifest of manifests) {
    for (const ep of manifest?.entry_points || []) {
      if (ep?.on_entity === entityType || ep?.on_entity === '*') {
        points.push({ ...ep, app_identifier: manifest.app_identifier });
      }
    }
  }
  if (points.length === 0) return null;

  const handle = async (point) => {
    await transferTask(
      point.task_type,
      buildPayload(entityType, entityId, entity, context),
      {
        app_identifier: point.app_identifier,
        title: `${point.label}: ${entity?.name ?? entityId}`,
        source_page: entityType === 'table' ? 'catalog-schema-detail' : 'catalog-data-product-detail',
        workspaceContext: {
          workspace: 'catalog',
          current_view: entityType === 'table' ? 'table_detail' : 'module_detail',
          entity_type: entityType,
          entity_id: entityId,
          entity_name: entity?.name ?? null,
          intent_signal: point.task_type,
          recent_actions: [],
        },
      },
    );
  };

  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
      {points.map((point) => {
        const Icon = ICON_MAP[point.icon] || AutoAwesomeIcon;
        return (
          <Button
            key={`${point.app_identifier}:${point.task_type}:${point.label}`}
            size="small"
            variant="outlined"
            startIcon={<Icon />}
            onClick={() => handle(point)}
          >
            {point.label}
          </Button>
        );
      })}
    </Box>
  );
}
