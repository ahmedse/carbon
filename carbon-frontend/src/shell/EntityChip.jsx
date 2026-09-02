// src/shell/EntityChip.jsx
// ────────────────────────────────────────────────────────────────────────────
// INLINE ENTITY CHIP for AI assistant messages (Phase F1-F).
//
// The assistant emits a `[[kind:id:label]]` token in its markdown; the
// MarkdownMessage remark plugin turns each token into an inline `<EntityChip/>`
// so users can jump straight from a mention to the Contextual Inspector
// (Notes drawer) for that entity.
//
// kind: 'table' | 'rule' | 'module' | 'org-unit'  (anything else → generic icon)
// id:   the entity's primary key (string, as captured from the token)
// label: human-readable name shown on the chip
// ────────────────────────────────────────────────────────────────────────────
import React from 'react';
import { Chip } from '@mui/material';
import TableChartIcon from '@mui/icons-material/TableChart';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import DescriptionIcon from '@mui/icons-material/Description';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import CategoryIcon from '@mui/icons-material/Category';
import { useNotes } from '../notes/NotesContext';

// Per-kind icon map. `kind` strings match the entityType values the Contextual
// Inspector tabs already match on (table / rule / module / org-unit).
const KIND_ICONS = {
  table: TableChartIcon,
  rule: FactCheckIcon,
  module: DescriptionIcon,
  'org-unit': AccountTreeIcon,
};

// Unknown/unrecognised kinds still get a neutral chip (not dropped).
const FALLBACK_ICON = CategoryIcon;

/**
 * @param {{ kind: string, id: string | number, label: string }} props
 */
export default function EntityChip({ kind, id, label }) {
  const { setContexts, setOpen } = useNotes();
  const Icon = KIND_ICONS[kind] || FALLBACK_ICON;

  const handleClick = () => {
    setContexts([{ entityType: kind, entityId: id, label }]);
    setOpen(true);
  };

  return (
    <Chip
      component="span"
      size="small"
      variant="outlined"
      icon={<Icon data-testid={`entity-chip-icon-${kind}`} fontSize="inherit" />}
      label={label}
      onClick={handleClick}
      aria-label={`Open ${label} in the Inspector`}
      title={`${kind}: ${label}`}
      sx={{ mx: 0.5, verticalAlign: 'middle' }}
    />
  );
}
