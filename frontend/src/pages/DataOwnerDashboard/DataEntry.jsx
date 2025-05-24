import React, { useEffect, useState } from "react";
import { Box, Typography, Button, TextField, MenuItem, Select, Paper } from "@mui/material";
import { useAuth } from "../../context/AuthContext";

const API_URL = "http://localhost:8000/api/entries/";
const TEMPLATE_URL = "http://localhost:8000/api/templates/";

export default function DataEntry({ context }) {
  const { user } = useAuth();
  const token = user?.token;
  const [template, setTemplate] = useState(null);
  const [form, setForm] = useState({});
  const [status, setStatus] = useState("");

  // Fetch template for current context (this assumes you have a way to select template by context)
  useEffect(() => {
    // For demo, fetch first template; in production, fetch by context/project/cycle
    fetch(TEMPLATE_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => res.json())
      .then(data => setTemplate(data[0])); // TODO: select by context
  }, [token, context]);

  const handleChange = e => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async () => {
    await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        template: template.id,
        template_version: template.version,
        context_id: context?.id,
        data: form,
      }),
    });
    setStatus("Submitted!");
  };

  if (!template) return <Typography>Loading template...</Typography>;

  return (
    <Paper sx={{ p: 3, mt: 2 }}>
      <Typography variant="h6">Enter Data: {template.name}</Typography>
      <form>
        {template.fields.map(field => (
          <Box key={field.id} mb={2}>
            <Typography fontWeight={500}>{field.name} {field.required && "*"}</Typography>
            {field.data_type === "number" && (
              <TextField fullWidth type="number" name={field.id} onChange={handleChange} required={field.required} />
            )}
            {field.data_type === "string" && (
              <TextField fullWidth name={field.id} onChange={handleChange} required={field.required} />
            )}
            {field.data_type === "date" && (
              <TextField fullWidth type="date" name={field.id} onChange={handleChange} required={field.required} InputLabelProps={{ shrink: true }} />
            )}
            {field.data_type === "select" && (
              <Select fullWidth name={field.id} onChange={handleChange} required={field.required}>
                {field.options.map(opt => (
                  <MenuItem key={opt} value={opt}>{opt}</MenuItem>
                ))}
              </Select>
            )}
          </Box>
        ))}
        <Button variant="contained" onClick={handleSubmit}>Submit</Button>
        {status && <Typography color="success.main">{status}</Typography>}
      </form>
    </Paper>
  );
}