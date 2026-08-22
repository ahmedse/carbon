// src/shell/AIDomainEntryPoints.jsx
// ONE AI button component ("Ask AI") that activates the Pulse with the
// current entity's context (table | module). Clicking the main button opens a
// context-scoped chat; a split-button arrow reveals the entity's
// domain-specific actions (manifest entry_points) — never one button per
// entry point. Dispatches via useAITaskTransfer.
import React, { useMemo, useState } from 'react';
import {
  Box, Button, ButtonGroup, Menu, MenuItem, ListItemIcon, ListItemText,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
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

function sourcePageFor(entityType) {
  return entityType === 'table' ? 'catalog-schema-detail' : 'catalog-data-product-detail';
}

function currentViewFor(entityType) {
  return entityType === 'table' ? 'table_detail' : 'module_detail';
}

export default function AIDomainEntryPoints({ entityType, entityId, entity, context }) {
  const { token } = useAuth();
  const { manifests } = useDomainManifests(token);
  const { transferTask } = useAITaskTransfer();
  const [anchorEl, setAnchorEl] = useState(null);

  const points = useMemo(() => {
    const out = [];
    for (const manifest of manifests) {
      for (const ep of manifest?.entry_points || []) {
        if (ep?.on_entity === entityType || ep?.on_entity === '*') {
          out.push({ ...ep, app_identifier: manifest.app_identifier });
        }
      }
    }
    // Dedupe identical (task_type, label) pairs so the generic chat offered
    // by every domain app is not repeated per app.
    const seen = new Set();
    return out.filter((point) => {
      const key = `${point.task_type}:${point.label}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [manifests, entityType]);

  // Domain-specific actions only; the generic chat lives on the main button.
  const actions = useMemo(() => points.filter((point) => point.task_type !== 'chat'), [points]);

  if (points.length === 0) return null;

  const closeMenu = () => setAnchorEl(null);

  const workspaceContext = (intentSignal) => ({
    workspace: 'catalog',
    current_view: currentViewFor(entityType),
    entity_type: entityType,
    entity_id: entityId,
    entity_name: entity?.name ?? null,
    intent_signal: intentSignal,
    recent_actions: [],
  });

  // Main button: activate the Pulse with the current entity's context.
  const handleAsk = () => {
    closeMenu();
    transferTask(
      'chat',
      buildPayload(entityType, entityId, entity, context),
      {
        title: `Ask about: ${entity?.name ?? entityId}`,
        source_page: sourcePageFor(entityType),
        workspaceContext: workspaceContext('chat'),
      },
    );
  };

  // Split-button arrow: entity-specific domain actions from the manifests.
  const handleAction = (point) => {
    closeMenu();
    transferTask(
      point.task_type,
      buildPayload(entityType, entityId, entity, context),
      {
        app_identifier: point.app_identifier,
        title: `${point.label}: ${entity?.name ?? entityId}`,
        source_page: sourcePageFor(entityType),
        workspaceContext: workspaceContext(point.task_type),
      },
    );
  };

  return (
    <Box>
      <ButtonGroup size="small" variant="outlined" color="primary" aria-label="Ask AI">
        <Button startIcon={<AutoAwesomeIcon />} onClick={handleAsk}>
          Ask AI
        </Button>
        {actions.length > 0 && (
          <Button
            aria-label="More AI actions"
            aria-haspopup="true"
            onClick={(event) => setAnchorEl(event.currentTarget)}
          >
            <ArrowDropDownIcon />
          </Button>
        )}
      </ButtonGroup>
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={closeMenu}>
        {actions.map((point) => {
          const Icon = ICON_MAP[point.icon] || AutoAwesomeIcon;
          return (
            <MenuItem
              key={`${point.app_identifier}:${point.task_type}:${point.label}`}
              onClick={() => handleAction(point)}
            >
              <ListItemIcon>
                <Icon fontSize="small" />
              </ListItemIcon>
              <ListItemText>{point.label}</ListItemText>
            </MenuItem>
          );
        })}
      </Menu>
    </Box>
  );
}
