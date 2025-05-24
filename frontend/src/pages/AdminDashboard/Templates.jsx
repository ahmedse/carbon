import React, { useEffect, useState } from "react";
import {
  Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Table, TableBody, TableCell, TableHead, TableRow, IconButton, MenuItem, Select
} from "@mui/material";
import { Add, Edit } from "@mui/icons-material";
import { useAuth } from "../../context/AuthContext";

const API_URL = "http://localhost:8000/api/datacollection/templates/";
const ITEM_DEFS_URL = "http://localhost:8000/api/datacollection/item-definitions/";

export default function Templates() {
  const { user } = useAuth();
  const token = user?.token;
  const [templates, setTemplates] = useState([]);
  const [itemDefs, setItemDefs] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    name: "", description: "", fields: []
  });

  useEffect(() => {
    fetch(API_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => res.json()).then(setTemplates);
    fetch(ITEM_DEFS_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => res.json()).then(setItemDefs);
  }, [token]);

  const handleChange = e => setForm({ ...form, [e.target.name]: e.target.value });
  const handleFieldsChange = e => setForm({ ...form, fields: Array.from(e.target.selectedOptions, opt => parseInt(opt.value)) });

  const handleOpen = (tpl = null) => {
    setEditing(tpl);
    setForm(tpl ? { ...tpl, fields: tpl.fields?.map(f => f.id) || [] } : { name: "", description: "", fields: [] });
    setOpen(true);
  };
  const handleClose = () => { setOpen(false); setEditing(null); };

  // Save template (simplified, without field ordering)
  const handleSubmit = async () => {
    const method = editing ? "PUT" : "POST";
    const url = editing ? `${API_URL}${editing.id}/` : API_URL;
    await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ ...form, fields: form.fields })
    });
    setOpen(false);
    fetch(API_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => res.json()).then(setTemplates);
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Templates</Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => handleOpen()}>Add Template</Button>
      </Box>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell><TableCell>Description</TableCell>
            <TableCell>Fields</TableCell><TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {templates.map(tpl => (
            <TableRow key={tpl.id}>
              <TableCell>{tpl.name}</TableCell>
              <TableCell>{tpl.description}</TableCell>
              <TableCell>{tpl.fields?.map(f => f.name).join(", ")}</TableCell>
              <TableCell>
                <IconButton onClick={() => handleOpen(tpl)}><Edit /></IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>{editing ? "Edit Template" : "Add Template"}</DialogTitle>
        <DialogContent>
          <TextField margin="dense" fullWidth label="Name" name="name" value={form.name} onChange={handleChange} />
          <TextField margin="dense" fullWidth label="Description" name="description" value={form.description} onChange={handleChange} />
          <Select
            multiple
            native
            fullWidth
            value={form.fields}
            onChange={handleFieldsChange}
            inputProps={{ id: "fields-select" }}
          >
            {itemDefs.map(def => (
              <option key={def.id} value={def.id}>{def.name} ({def.data_type})</option>
            ))}
          </Select>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}