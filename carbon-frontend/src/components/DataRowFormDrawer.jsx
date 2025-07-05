// File: src/components/DataRowFormDrawer.jsx

import React, { useState, useEffect } from "react";
import {
  Box, TextField, MenuItem, Checkbox, FormControlLabel, Button, Typography
} from "@mui/material";
import FileCellRenderer from "./FileCellRenderer";
import { DatePicker } from "@mui/x-date-pickers";
import dayjs from "dayjs";
import { useNotification } from "./NotificationProvider";

// Helper to validate a single value based on field config
function validateField(field, value) {
  if (
    field.required &&
    (value === "" ||
      value === null ||
      value === undefined ||
      (Array.isArray(value) && value.length === 0))
  ) {
    return `${field.label} is required.`;
  }
  // Validation JSON
  if (field.validation) {
    try {
      const rules =
        typeof field.validation === "string"
          ? JSON.parse(field.validation)
          : field.validation;
      // String: regex
      if (rules.regex && typeof value === "string" && value) {
        const re = new RegExp(rules.regex);
        if (!re.test(value))
          return rules.message || `Invalid format.`;
      }
      // Number: min/max
      if (typeof value === "number" || field.type === "number") {
        const num = Number(value);
        if (rules.min !== undefined && num < rules.min)
          return `Must be ≥ ${rules.min}`;
        if (rules.max !== undefined && num > rules.max)
          return `Must be ≤ ${rules.max}`;
      }
      // String: min/max length
      if (typeof value === "string") {
        if (
          rules.minLength !== undefined &&
          value.length < rules.minLength
        )
          return `Must be at least ${rules.minLength} chars`;
        if (
          rules.maxLength !== undefined &&
          value.length > rules.maxLength
        )
          return `Must be at most ${rules.maxLength} chars`;
      }
      // Array: minItems/maxItems
      if (Array.isArray(value)) {
        if (
          rules.minItems !== undefined &&
          value.length < rules.minItems
        )
          return `Select at least ${rules.minItems}`;
        if (
          rules.maxItems !== undefined &&
          value.length > rules.maxItems
        )
          return `Select at most ${rules.maxItems}`;
      }
    } catch (e) {
      // ignore validation parse error, fail open
    }
  }
  return null;
}

export default function DataRowFormDrawer({
  open,
  onClose,
  fields = [],
  initial,
  onSubmit,
  token,
  project_id,
  module_id,
  uploadRowFile,
  rowId,
  mode,
}) {
  const [values, setValues] = useState({});
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const notifyContext = useNotification();
  // Defensive: ensure notify is always a function
  const notify = (notifyContext && typeof notifyContext.notify === "function")
    ? notifyContext.notify
    : (msg) => window.alert(typeof msg === "string" ? msg : (msg?.message ?? "Notification"));

  useEffect(() => {
    setValues(initial?.values || {});
    setErrors({});
  }, [initial]);

  const handleChange = (field, value) => {
    setValues((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const validateAll = () => {
    const newErrors = {};
    (fields || []).forEach((field) => {
      if (!field.is_active) return;
      const val = values[field.name];
      const err = validateField(field, val);
      if (err) newErrors[field.name] = err;
    });
    setErrors(newErrors);
    return newErrors;
  };

  const handleSubmit = async () => {
    const newErrors = validateAll();
    if (Object.keys(newErrors).length) {
      notify({ message: "Please fix errors in the form.", type: "error" });
      return;
    }
    setSubmitting(true);
    try {
      // Convert dayjs to string for dates
      const submitVals = { ...values };
      (fields || []).forEach((f) => {
        if (
          f.type === "date" &&
          submitVals[f.name] &&
          typeof submitVals[f.name]?.isValid === "function"
        ) {
          submitVals[f.name] = submitVals[f.name].toISOString
            ? submitVals[f.name].toISOString()
            : submitVals[f.name].format("YYYY-MM-DD");
        }
      });
      await onSubmit(submitVals, rowId);
    } catch (err) {
      notify({
        message: err?.message || "Failed to save row",
        type: "error",
      });
    }
    setSubmitting(false);
  };

  return (
    <Box width="100%">
      <Box display="flex" flexDirection="column" gap={2} p={1}>
        {(fields || []).map((field) => {
          if (!field.is_active) return null;
          const fieldError = errors[field.name];
          const commonProps = {
            label: field.label + (field.required ? " *" : ""),
            value:
              values[field.name] ??
              (field.type === "multiselect" ? [] : ""),
            onChange: (e) =>
              handleChange(
                field.name,
                field.type === "boolean"
                  ? e.target.checked
                  : field.type === "multiselect"
                  ? e.target.value
                  : e.target.value
              ),
            error: !!fieldError,
            helperText: fieldError,
            fullWidth: true,
            required: !!field.required,
            disabled: submitting,
          };

          if (field.type === "string" || field.type === "number") {
            return (
              <TextField
                key={field.name}
                {...commonProps}
                type={field.type === "number" ? "number" : "text"}
              />
            );
          }
          if (field.type === "text") {
            return (
              <TextField
                key={field.name}
                {...commonProps}
                multiline
              />
            );
          }
          if (field.type === "boolean") {
            return (
              <FormControlLabel
                key={field.name}
                control={
                  <Checkbox
                    checked={!!values[field.name]}
                    onChange={commonProps.onChange}
                    disabled={submitting}
                  />
                }
                label={field.label + (field.required ? " *" : "")}
              />
            );
          }
          if (field.type === "date") {
            return (
              <DatePicker
                key={field.name}
                label={field.label + (field.required ? " *" : "")}
                value={
                  values[field.name]
                    ? dayjs(values[field.name])
                    : null
                }
                onChange={(val) => handleChange(field.name, val)}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    error: !!fieldError,
                    helperText: fieldError,
                    required: !!field.required,
                  },
                }}
                disabled={submitting}
              />
            );
          }
          if (field.type === "select") {
            return (
              <TextField
                key={field.name}
                {...commonProps}
                select
              >
                {(field.options || []).map((opt) => (
                  <MenuItem value={opt.value} key={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </TextField>
            );
          }
          if (field.type === "multiselect") {
            return (
              <TextField
                key={field.name}
                {...commonProps}
                select
                SelectProps={{ multiple: true }}
              >
                {(field.options || []).map((opt) => (
                  <MenuItem value={opt.value} key={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </TextField>
            );
          }
          if (field.type === "file") {
            // Only allow file upload if editing existing row
            if (!rowId && mode === "add") {
              return (
                <Box
                  key={field.name}
                  display="flex"
                  alignItems="center"
                  gap={2}
                >
                  <Typography variant="body2" color="textSecondary">
                    {field.label}: Save row before uploading file.
                  </Typography>
                </Box>
              );
            }
            return (
              <FileCellRenderer
                key={field.name}
                value={values[field.name]}
                onChange={(val) => handleChange(field.name, val)}
                rowId={rowId}
                fieldName={field.name}
                uploadRowFile={uploadRowFile}
                token={token}
                project_id={project_id}
                module_id={module_id}
                disabled={submitting}
              />
            );
          }
          return null;
        })}
      </Box>
      <Box display="flex" gap={2} mt={2}>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={submitting}
        >
          Save
        </Button>
      </Box>
    </Box>
  );
}