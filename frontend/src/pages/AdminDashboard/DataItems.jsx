// frontend/src/pages/AdminDashboard/DataItems.jsx

import React, { useEffect, useState } from "react";
import {
  Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Table, TableBody, TableCell, TableHead, TableRow, IconButton, Select, MenuItem
} from "@mui/material";
import { Add, Edit } from "@mui/icons-material";
import { useAuth } from "../../context/AuthContext";
import { apiFetch } from "../../api";
import { API_BASE_URL, API_ROUTES } from "../../config";

const API_URL = `${API_BASE_URL}${API_ROUTES.dataItemDefs}`;

const dataTypes = [
  { value: "number", label: "Number" },
  { value: "string", label: "String" },
  { value: "date", label: "Date" },
  { value: "file", label: "File" },
  { value: "select", label: "Select" },
];

export default function DataItems() {
  const { user, currentContext } = useAuth();
  const token = user?.token;
  // extract context_type and context_name from currentContext
  const context_type = currentContext?.context_type;
  const context_name = currentContext?.[context_type];
  const context = { context_type, context_name };

  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    name: "", description: "", data_type: "number", required: true, units: "", options: []
  });

  // Fetch items
  useEffect(() => {
    if (!token || !context_type || !context_name) return;
    apiFetch("/api/datacollection/item-definitions/", { token, context })
      .then(res => res.json()).then(setItems);
  }, [token, context_type, context_name]);

  // Handle form input
  const handleChange = e => setForm({ ...form, [e.target.name]: e.target.value });

  // Open dialog for add/edit
  const handleOpen = (item = null) => {
    setEditing(item);
    setForm(item ? { ...item, options: item.options?.join(",") || "" } : { name: "", description: "", data_type: "number", required: true, units: "", options: "" });
    setOpen(true);
  };

  const handleClose = () => { setOpen(false); setEditing(null); };

  // Submit form (add or edit)
  const handleSubmit = async () => {
    const method = editing ? "PUT" : "POST";
    const endpoint = editing ? `/api/datacollection/item-definitions/${editing.id}/` : "/api/datacollection/item-definitions/";
    const body = {
      ...form,
      options: form.data_type === "select" ? form.options.split(",").map(opt => opt.trim()) : []
    };
    await apiFetch(endpoint, { method, body, token, context });
    setOpen(false);
    // Refresh items
    apiFetch("/api/datacollection/item-definitions/", { token, context })
      .then(res => res.json()).then(setItems);
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">Data Item Definitions</Typography>
        <Button variant="contained" startIcon={<Add />} onClick={() => handleOpen()}>Add Item</Button>
      </Box>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell><TableCell>Type</TableCell>
            <TableCell>Required</TableCell><TableCell>Units</TableCell>
            <TableCell>Options</TableCell><TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map(item => (
            <TableRow key={item.id}>
              <TableCell>{item.name}</TableCell>
              <TableCell>{item.data_type}</TableCell>
              <TableCell>{item.required ? "Yes" : "No"}</TableCell>
              <TableCell>{item.units}</TableCell>
              <TableCell>{item.options?.join(", ")}</TableCell>
              <TableCell>
                <IconButton onClick={() => handleOpen(item)}><Edit /></IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>{editing ? "Edit Data Item" : "Add Data Item"}</DialogTitle>
        <DialogContent>
          <TextField margin="dense" fullWidth label="Name" name="name" value={form.name} onChange={handleChange} />
          <TextField margin="dense" fullWidth label="Description" name="description" value={form.description} onChange={handleChange} />
          <Select fullWidth name="data_type" value={form.data_type} onChange={handleChange}>
            {dataTypes.map(dt => (
              <MenuItem key={dt.value} value={dt.value}>{dt.label}</MenuItem>
            ))}
          </Select>
          <TextField margin="dense" fullWidth label="Units" name="units" value={form.units} onChange={handleChange} />
          {form.data_type === "select" && (
            <TextField margin="dense" fullWidth label="Options (comma separated)" name="options" value={form.options} onChange={handleChange} />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}