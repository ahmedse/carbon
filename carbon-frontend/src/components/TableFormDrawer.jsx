import React, { useState, useEffect } from "react";
import { Drawer, Box, TextField, Button, Typography, Select, MenuItem } from "@mui/material";
import MicroHelp from "./MicroHelp";

export default function TableFormDrawer({ open, onClose, onSubmit, modules, initial, lang }) {
  const [title, setTitle] = useState(initial?.title || "");
  const [desc, setDesc] = useState(initial?.description || "");
  const [moduleId, setModuleId] = useState(initial?.module || modules?.[0]?.id || "");

  useEffect(() => {
    setTitle(initial?.title || "");
    setDesc(initial?.description || "");
    setModuleId(initial?.module || modules?.[0]?.id || "");
  }, [initial, modules]);

  // Robust: Only allow moduleId that exists in modules
  const validModuleIds = modules.map(m => String(m.id));
  const safeModuleId = validModuleIds.includes(String(moduleId)) ? moduleId : (validModuleIds[0] || "");

  const handleSubmit = () => {
    if (!title.trim()) return;
    onSubmit({ title, description: desc, module: safeModuleId });
  };

  return (
    <Drawer open={open} onClose={onClose} anchor="right" PaperProps={{ sx: { width: 440 } }}>
      <Box p={3} display="flex" flexDirection="column" gap={2}>
        <Typography variant="h6">Table</Typography>
        <Select
          value={safeModuleId}
          label="Module"
          onChange={e => setModuleId(e.target.value)}
        >
          {modules.map(m => (
            <MenuItem value={m.id} key={m.id}>{m.name}</MenuItem>
          ))}
        </Select>
        <TextField
          label={<><span>Title</span> <MicroHelp helpKey="table.title" lang={lang} /></>}
          value={title}
          onChange={e => setTitle(e.target.value)}
          fullWidth
        />
        <TextField
          label={<><span>Description</span> <MicroHelp helpKey="table.desc" lang={lang} /></>}
          value={desc}
          onChange={e => setDesc(e.target.value)}
          fullWidth
          multiline
        />
        <Box mt={2} display="flex" justifyContent="flex-end" gap={2}>
          <Button onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" disabled={!title.trim()}>Save</Button>
        </Box>
      </Box>
    </Drawer>
  );
}