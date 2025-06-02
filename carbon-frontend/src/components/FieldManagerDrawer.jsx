import React, { useState } from "react";
import {
  Drawer, Typography, IconButton, Button, Box, Paper
} from "@mui/material";
import { Close, Add, Edit, Delete, DragIndicator } from "@mui/icons-material";
import FieldForm from "./FieldForm";
import { DndContext, closestCenter } from "@dnd-kit/core";
import { arrayMove, SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from '@dnd-kit/utilities';

function SortableFieldRow({ field, idx, onEdit, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: field.id });

  return (
    <Box
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        background: isDragging ? "#f0f0f0" : "inherit"
      }}
      display="flex"
      alignItems="center"
      borderBottom="1px solid #eee"
      px={1}
      py={1}
      gap={1}
    >
      <IconButton {...attributes} {...listeners}><DragIndicator /></IconButton>
      <Box flex={1}>
        <Typography fontWeight="bold">{field.label}</Typography>
        <Typography variant="caption" color="text.secondary">{field.type}</Typography>
      </Box>
      <IconButton onClick={() => onEdit(field)}><Edit fontSize="small" /></IconButton>
      <IconButton onClick={() => onDelete(field)}><Delete fontSize="small" /></IconButton>
    </Box>
  );
}

export default function FieldManagerDrawer({
  open, onClose, fields, onSaveOrder, onEditField, onAddField, onDeleteField, lang
}) {
  const [editingField, setEditingField] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [items, setItems] = useState(fields.map(f => f.id));

  // Update local drag order if fields prop changes (reopen, etc)
  React.useEffect(() => {
    setItems(fields.map(f => f.id));
  }, [fields]);

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (active.id !== over.id) {
      const oldIndex = items.indexOf(active.id);
      const newIndex = items.indexOf(over.id);
      const newItems = arrayMove(items, oldIndex, newIndex);
      setItems(newItems);

      // Map fields to new order and call onSaveOrder
      const newFields = newItems.map((id, idx) => {
        const field = fields.find(f => f.id === id);
        return { ...field, order: idx };
      });
      onSaveOrder(newFields);
    }
  };

  // Fields in current display order:
  const orderedFields = items.map(id => fields.find(f => f.id === id)).filter(Boolean);

  return (
    <Drawer open={open} onClose={onClose} anchor="right" PaperProps={{ sx: { width: 500 } }}>
      <Box p={2}>
        <Box display="flex" alignItems="center">
          <Typography variant="h6" flex={1}>Field Manager</Typography>
          <IconButton onClick={onClose}><Close /></IconButton>
        </Box>
        <Button startIcon={<Add />} sx={{ my: 2 }} onClick={() => { setAddOpen(true); setEditingField(null); }}>
          Add Field
        </Button>
        <Paper elevation={0} sx={{ mb: 2 }}>
          <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={items} strategy={verticalListSortingStrategy}>
              {orderedFields.map((field, idx) => (
                <SortableFieldRow
                  key={field.id}
                  field={field}
                  idx={idx}
                  onEdit={f => { setEditingField(f); setAddOpen(true); }}
                  onDelete={onDeleteField}
                />
              ))}
            </SortableContext>
          </DndContext>
        </Paper>
      </Box>
      {/* Add/Edit Field Drawer */}
      {addOpen && (
        <Drawer open={addOpen} onClose={() => setAddOpen(false)} anchor="right" PaperProps={{ sx: { width: 460 } }}>
          <FieldForm
            initial={editingField}
            lang={lang}
            onSubmit={data => {
              setAddOpen(false);
              setEditingField(null);
              if (editingField) onEditField(editingField, data);
              else onAddField(data);
            }}
            onCancel={() => { setAddOpen(false); setEditingField(null); }}
          />
        </Drawer>
      )}
    </Drawer>
  );
}