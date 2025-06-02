import React, { useEffect, useState } from "react";
import {
  TextField, MenuItem, Checkbox, FormControlLabel, Box, Button, Typography
} from "@mui/material";
import MicroHelp from "./MicroHelp";
import FieldOptionsTable from "./FieldOptionsTable";

const FIELD_TYPES = [
  { value: "string", label: "String" },
  { value: "text", label: "Text (Multiline)" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
  { value: "boolean", label: "Boolean" },
  { value: "select", label: "Single Select" },
  { value: "multiselect", label: "Multi Select" },
  { value: "file", label: "File" },
  { value: "reference", label: "Reference" },
];

export default function FieldForm({ initial, onSubmit, onCancel, lang }) {
  const [name, setName] = useState(initial?.name || "");
  const [label, setLabel] = useState(initial?.label || "");
  const [type, setType] = useState(initial?.type || "string");
  const [desc, setDesc] = useState(initial?.description || "");
  const [required, setRequired] = useState(initial?.required || false);
  const [order, setOrder] = useState(initial?.order ?? 0);
  const [validation, setValidation] = useState(initial?.validation ? JSON.stringify(initial.validation, null, 2) : "");
  const [validationErr, setValidationErr] = useState("");
  const [options, setOptions] = useState(Array.isArray(initial?.options) ? initial.options : []);

  useEffect(() => {
    if (!["select", "multiselect"].includes(type)) setOptions([]);
  }, [type]);

  const handleValidationChange = (e) => {
    setValidation(e.target.value);
    try {
      if (e.target.value.trim()) JSON.parse(e.target.value);
      setValidationErr("");
    } catch (err) {
      setValidationErr("Invalid JSON");
    }
  };

  const handleSubmit = () => {
    let validationObj = undefined;
    if (validation.trim()) {
      try {
        validationObj = JSON.parse(validation);
      } catch {
        setValidationErr("Invalid JSON");
        return;
      }
    }
    onSubmit({
      name, label, type, description: desc, required, order: Number(order),
      validation: validationObj, options: options.length > 0 ? options : undefined
    });
  };

  // Robust: Only allow type that exists in FIELD_TYPES
  const validTypes = FIELD_TYPES.map(f => f.value);
  const safeType = validTypes.includes(type) ? type : validTypes[0];

  return (
    <Box display="flex" flexDirection="column" gap={2} p={1} sx={{ pt: { xs: 7, sm: 8 } }}>
      <TextField
        label={<><span>Name</span> <MicroHelp helpKey="field.name" lang={lang} /></>}
        value={name}
        onChange={e => setName(e.target.value)}
        fullWidth
        helperText="No spaces, English letters/numbers only."
      />
      <TextField
        label={<><span>Label</span> <MicroHelp helpKey="field.label" lang={lang} /></>}
        value={label}
        onChange={e => setLabel(e.target.value)}
        fullWidth
      />
      <TextField
        select
        label={<><span>Type</span> <MicroHelp helpKey="field.type" lang={lang} /></>}
        value={safeType}
        onChange={e => setType(e.target.value)}
        fullWidth
      >
        {FIELD_TYPES.map(opt => (
          <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
        ))}
      </TextField>
      <TextField
        label={<><span>Description</span> <MicroHelp helpKey="field.desc" lang={lang} /></>}
        value={desc}
        onChange={e => setDesc(e.target.value)}
        fullWidth
        multiline
      />
      <Box display="flex" alignItems="center" gap={2}>
        <FormControlLabel
          control={
            <Checkbox checked={required} onChange={e => setRequired(e.target.checked)} />
          }
          label={<><span>Required</span> <MicroHelp helpKey="field.required" lang={lang} /></>}
        />
        <TextField
          label={<><span>Order</span> <MicroHelp helpKey="field.order" lang={lang} /></>}
          value={order}
          type="number"
          onChange={e => setOrder(e.target.value)}
          size="small"
          sx={{ width: 120 }}
        />
      </Box>
      <TextField
        label={
          <Box display="flex" alignItems="center">
            <span>Validation (JSON)</span>
            <MicroHelp helpKey="field.validation" lang={lang} />
            <Button size="small" onClick={() => setValidation(`{ "min": 1, "max": 10, "regexp": "^\\w+$" }`)} sx={{ ml: 1 }}>
              Example
            </Button>
          </Box>
        }
        value={validation}
        onChange={handleValidationChange}
        fullWidth
        multiline
        minRows={2}
        error={!!validationErr}
        helperText={validationErr || "Use JSON for advanced validation (e.g. min, max, regexp)."}
      />
      {["select", "multiselect"].includes(safeType) && (
        <FieldOptionsTable value={options} onChange={setOptions} lang={lang} />
      )}
      <Box display="flex" justifyContent="flex-end" gap={2} mt={2}>
        <Button onClick={onCancel}>Cancel</Button>
        <Button onClick={handleSubmit} disabled={!name || !label || !!validationErr} variant="contained">
          Save
        </Button>
      </Box>
    </Box>
  );
}