import React from "react";
import { Table, TableHead, TableRow, TableCell, TableBody, IconButton, TextField, Button } from "@mui/material";
import { Delete, Add } from "@mui/icons-material";
import MicroHelp from "./MicroHelp";

export default function FieldOptionsTable({ value, onChange, lang }) {
  const handleEdit = (idx, key, val) => {
    const updated = value.map((row, i) => i === idx ? { ...row, [key]: val } : row);
    onChange(updated);
  };
  const handleAdd = () => onChange([...value, { label: "", value: "" }]);
  const handleDelete = idx => onChange(value.filter((_, i) => i !== idx));

  return (
    <div>
      <Button onClick={handleAdd} startIcon={<Add />} size="small">Add Option</Button>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Label <MicroHelp helpKey="field.options" lang={lang} /></TableCell>
            <TableCell>Value</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {value.map((row, idx) => (
            <TableRow key={idx}>
              <TableCell>
                <TextField
                  value={row.label}
                  onChange={e => handleEdit(idx, "label", e.target.value)}
                  size="small"
                  fullWidth
                />
              </TableCell>
              <TableCell>
                <TextField
                  value={row.value}
                  onChange={e => handleEdit(idx, "value", e.target.value)}
                  size="small"
                  fullWidth
                />
              </TableCell>
              <TableCell>
                <IconButton onClick={() => handleDelete(idx)} size="small"><Delete /></IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}